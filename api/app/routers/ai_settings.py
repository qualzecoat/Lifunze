"""Router Pengaturan AI — koneksi AI per akun guru/admin (pola Rephore).

Konfigurasi generik OpenAI-compatible: nama koneksi, base URL, API key
(terenkripsi Fernet di DB, tidak pernah dikembalikan utuh), fetch daftar
model dari {base_url}/models, pilih model, tes koneksi.
"""

import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..ai_akses import MODE_BAGI, PERAN_BOLEH, daftar_tersedia, target_ids
from ..db import get_db
from ..deps import require_csrf, require_roles
from ..models import AiSetting, AiSettingTarget, User
from ..security import decrypt_secret, encrypt_secret, mask_secret
from ..url_safety import UnsafeUrlError, assert_public_target, normalize_ai_base_url

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
guru_admin = require_roles("guru", "admin")
admin_saja = require_roles("admin")

HTTP_TIMEOUT = 20.0


def http_client() -> httpx.Client:
    """Dipisah agar mudah di-mock saat pengujian."""
    return httpx.Client(timeout=HTTP_TIMEOUT)


def setting_out(db: Session, s: AiSetting, viewer: User | None = None) -> dict:
    milik_saya = viewer is None or viewer.id == s.user_id
    if milik_saya:
        try:
            masked = mask_secret(decrypt_secret(s.api_key_encrypted))
        except RuntimeError:
            masked = "(tidak bisa dibaca)"
    else:
        # Penerima pengaturan bersama TIDAK melihat topeng kunci admin.
        masked = None
    pemilik = db.get(User, s.user_id) if not milik_saya else None
    return {
        "id": s.id,
        "nama": s.nama,
        "base_url": s.base_url,
        "model": s.model,
        "is_default": s.is_default,
        "api_key_masked": masked,
        "milik_saya": milik_saya,
        "pemilik": (pemilik.nama_lengkap or pemilik.username) if pemilik else None,
        "dibagikan_mode": s.dibagikan_mode or "tidak",
        "target_ids": target_ids(db, s.id) if milik_saya else [],
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _terapkan_distribusi(
    db: Session,
    user: User,
    s: AiSetting,
    mode: str | None,
    targets: list[int] | None,
) -> None:
    """Atur mode berbagi + daftar target sebuah pengaturan (khusus admin)."""
    if user.role != "admin":
        if (mode is not None and mode != "tidak") or targets:
            raise HTTPException(
                status_code=400,
                detail="Hanya admin yang dapat membagikan Pengaturan AI ke akun lain.",
            )
        return
    mode_baru = mode if mode is not None else (s.dibagikan_mode or "tidak")
    if mode_baru not in MODE_BAGI:
        raise HTTPException(status_code=400, detail=f"Mode berbagi tidak dikenal: {mode_baru}.")
    s.dibagikan_mode = mode_baru
    if targets is not None:
        valid = {
            u.id
            for u in db.query(User)
            .filter(User.role.in_(PERAN_BOLEH), User.id != user.id)
            .all()
        }
        asing = [i for i in targets if i not in valid]
        if asing:
            raise HTTPException(
                status_code=400,
                detail=f"Akun target tidak valid (harus guru/admin lain): {asing}.",
            )
        db.query(AiSettingTarget).filter(AiSettingTarget.setting_id == s.id).delete(
            synchronize_session=False
        )
        for uid in dict.fromkeys(targets):
            db.add(AiSettingTarget(setting_id=s.id, user_id=uid))


def _base_atau_400(raw: str) -> str:
    """Audit #12: base URL wajib lolos pagar SSRF sebelum disimpan/dipakai."""
    try:
        return normalize_ai_base_url(raw)
    except UnsafeUrlError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _pastikan_tujuan_publik(url: str) -> None:
    try:
        assert_public_target(url)
    except UnsafeUrlError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _own_setting(db: Session, user: User, setting_id: int) -> AiSetting:
    s = db.get(AiSetting, setting_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Pengaturan AI tidak ditemukan.")
    return s


def _apply_default(db: Session, user: User, target: AiSetting) -> None:
    db.query(AiSetting).filter(
        AiSetting.user_id == user.id, AiSetting.id != target.id
    ).update({AiSetting.is_default: False}, synchronize_session=False)
    target.is_default = True


class SettingIn(BaseModel):
    nama: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1)
    model: Optional[str] = None
    is_default: bool = False
    dibagikan_mode: str = "tidak"  # khusus admin: tidak|semua|whitelist|blacklist
    target_ids: list[int] = []


class SettingPatchIn(BaseModel):
    nama: Optional[str] = Field(default=None, min_length=1, max_length=120)
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    api_key: Optional[str] = None  # kosong/None = tidak diubah
    model: Optional[str] = None
    is_default: Optional[bool] = None
    dibagikan_mode: Optional[str] = None
    target_ids: Optional[list[int]] = None


@router.get("/settings/recipients")
def list_recipients(user: User = Depends(admin_saja), db: Session = Depends(get_db)):
    """Daftar akun yang bisa menjadi target whitelist/blacklist admin."""
    rows = (
        db.query(User)
        .filter(User.role.in_(PERAN_BOLEH), User.id != user.id)
        .order_by(User.role, User.nama_lengkap, User.username)
        .all()
    )
    return [
        {
            "id": u.id,
            "username": u.username,
            "nama": u.nama_lengkap or u.username,
            "role": u.role,
        }
        for u in rows
    ]


@router.get("/settings")
def list_settings(user: User = Depends(guru_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(AiSetting)
        .filter(AiSetting.user_id == user.id)
        .order_by(AiSetting.is_default.desc(), AiSetting.nama)
        .all()
    )
    bersama = [s for s in daftar_tersedia(db, user) if s.user_id != user.id]
    return [setting_out(db, s, user) for s in rows + bersama]


@router.post("/settings", status_code=201, dependencies=[Depends(require_csrf)])
def create_setting(
    body: SettingIn,
    user: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    s = AiSetting(
        user_id=user.id,
        nama=body.nama.strip(),
        base_url=_base_atau_400(body.base_url),
        api_key_encrypted=encrypt_secret(body.api_key.strip()),
        model=(body.model or "").strip() or None,
        is_default=False,
    )
    db.add(s)
    db.flush()
    _terapkan_distribusi(db, user, s, body.dibagikan_mode, body.target_ids)
    if body.is_default or db.query(AiSetting).filter(AiSetting.user_id == user.id).count() == 1:
        _apply_default(db, user, s)
    db.commit()
    db.refresh(s)
    return setting_out(db, s, user)


@router.patch("/settings/{setting_id}", dependencies=[Depends(require_csrf)])
def update_setting(
    setting_id: int,
    body: SettingPatchIn,
    user: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    s = _own_setting(db, user, setting_id)
    if body.nama is not None:
        s.nama = body.nama.strip()
    if body.base_url is not None:
        s.base_url = _base_atau_400(body.base_url)
    if body.api_key:
        s.api_key_encrypted = encrypt_secret(body.api_key.strip())
    if body.model is not None:
        s.model = body.model.strip() or None
    if body.is_default:
        _apply_default(db, user, s)
    _terapkan_distribusi(db, user, s, body.dibagikan_mode, body.target_ids)
    db.commit()
    db.refresh(s)
    return setting_out(db, s, user)


@router.delete("/settings/{setting_id}", dependencies=[Depends(require_csrf)])
def delete_setting(
    setting_id: int,
    user: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    s = _own_setting(db, user, setting_id)
    # Audit #5: lepas rujukan riwayat job generate (FK tanpa cascade bisa
    # menahan penghapusan di PostgreSQL).
    from ..models import GenerationJob

    db.query(GenerationJob).filter(GenerationJob.ai_setting_id == s.id).update(
        {GenerationJob.ai_setting_id: None}, synchronize_session=False
    )
    db.query(AiSettingTarget).filter(AiSettingTarget.setting_id == s.id).delete(
        synchronize_session=False
    )
    db.delete(s)
    db.commit()
    return {"ok": True}


class FetchModelsIn(BaseModel):
    base_url: str
    api_key: Optional[str] = None
    setting_id: Optional[int] = None  # bila api_key kosong: pakai key tersimpan milik setting ini


@router.post("/settings/fetch-models", dependencies=[Depends(require_csrf)])
def fetch_models(
    body: FetchModelsIn,
    user: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    """Ambil daftar model dari {base_url}/models (OpenAI-compatible)."""
    api_key = (body.api_key or "").strip()
    if not api_key and body.setting_id is not None:
        api_key = decrypt_secret(_own_setting(db, user, body.setting_id).api_key_encrypted)
    if not api_key:
        raise HTTPException(status_code=400, detail="API key wajib diisi untuk mengambil daftar model.")
    base = _base_atau_400(body.base_url)
    _pastikan_tujuan_publik(f"{base}/models")
    try:
        with http_client() as client:
            res = client.get(f"{base}/models", headers={"Authorization": f"Bearer {api_key}"})
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Tidak bisa menghubungi provider: {e}")
    if res.status_code >= 400:
        raise HTTPException(
            status_code=400,
            detail=f"Provider menolak ({res.status_code}). Periksa base URL & API key.",
        )
    try:
        data = res.json()
        models = sorted(m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m)
    except Exception:
        raise HTTPException(status_code=400, detail="Respons provider tidak sesuai format OpenAI-compatible.")
    return {"models": models}


@router.post("/settings/{setting_id}/test", dependencies=[Depends(require_csrf)])
def test_connection(
    setting_id: int,
    user: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    """Tes koneksi sungguhan: satu chat completion mini ke provider."""
    s = _own_setting(db, user, setting_id)
    if not s.model:
        raise HTTPException(status_code=400, detail="Pilih model dulu sebelum tes koneksi.")
    api_key = decrypt_secret(s.api_key_encrypted)
    payload = {
        "model": s.model,
        "messages": [{"role": "user", "content": "Balas dengan kata: OK"}],
        "max_tokens": 4,
        "temperature": 0,
    }
    start = time.monotonic()
    _pastikan_tujuan_publik(f"{s.base_url}/chat/completions")
    try:
        with http_client() as client:
            res = client.post(
                f"{s.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Tidak bisa menghubungi provider: {e}")
    latency_ms = int((time.monotonic() - start) * 1000)
    if res.status_code >= 400:
        snippet = res.text[:200].replace("\n", " ")
        raise HTTPException(status_code=400, detail=f"Provider menolak ({res.status_code}): {snippet}")
    return {"ok": True, "model": s.model, "latency_ms": latency_ms, "pesan": "Koneksi AI berhasil."}
