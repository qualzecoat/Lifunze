"""Akses Pengaturan AI bersama (distribusi admin, 2026-10-21).

Satu-satunya tempat yang memutuskan apakah sebuah AiSetting boleh
dipakai akun lain:
- Pemilik selalu boleh memakai pengaturannya sendiri.
- Pengaturan milik ADMIN dengan mode "semua" boleh dipakai semua
  guru/admin; "whitelist" hanya akun target; "blacklist" semua kecuali
  target. Pengaturan non-admin tidak pernah terbagikan.
- Resolusi default untuk generate: milik sendiri dulu (default sendiri,
  lalu pengaturan sendiri pertama); pengaturan bersama hanya CADANGAN
  bila akun belum punya pengaturan sendiri — dan selalu bisa dipilih
  eksplisit lewat ai_setting_id.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import AiSetting, AiSettingTarget, User

MODE_BAGI = ("tidak", "semua", "whitelist", "blacklist")
PERAN_BOLEH = ("guru", "admin")


def target_ids(db: Session, setting_id: int) -> list[int]:
    return [
        r.user_id
        for r in db.query(AiSettingTarget)
        .filter(AiSettingTarget.setting_id == setting_id)
        .all()
    ]


def tersedia_untuk(db: Session, s: AiSetting, user: User) -> bool:
    if s.user_id == user.id:
        return True
    if user.role not in PERAN_BOLEH:
        return False
    owner = db.get(User, s.user_id)
    if owner is None or owner.role != "admin":
        return False
    mode = s.dibagikan_mode or "tidak"
    if mode == "semua":
        return True
    if mode == "whitelist":
        return user.id in target_ids(db, s.id)
    if mode == "blacklist":
        return user.id not in target_ids(db, s.id)
    return False


def daftar_tersedia(db: Session, user: User) -> list[AiSetting]:
    """Semua pengaturan yang boleh dipakai user: miliknya + yang
    dibagikan admin kepadanya."""
    rows = db.query(AiSetting).order_by(AiSetting.id).all()
    return [s for s in rows if tersedia_untuk(db, s, user)]


def resolusi_setting(db: Session, user: User, setting_id: int | None) -> AiSetting:
    if setting_id is not None:
        s = db.get(AiSetting, setting_id)
        if s is None or not tersedia_untuk(db, s, user):
            raise HTTPException(status_code=404, detail="Pengaturan AI tidak ditemukan.")
        return s
    milik = (
        db.query(AiSetting)
        .filter(AiSetting.user_id == user.id)
        .order_by(AiSetting.is_default.desc(), AiSetting.id)
        .all()
    )
    if milik:
        return milik[0]
    bersama = [s for s in daftar_tersedia(db, user) if s.user_id != user.id]
    if bersama:
        # Yang ditandai default oleh adminnya didahulukan, lalu tertua.
        bersama.sort(key=lambda s: (not s.is_default, s.id))
        return bersama[0]
    raise HTTPException(
        status_code=400,
        detail="Anda belum punya Pengaturan AI dan belum ada yang dibagikan admin. "
        "Buat dulu di menu Pengaturan AI (base URL, API key, model).",
    )
