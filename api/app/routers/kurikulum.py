"""Router Kurikulum kelas (2026-10-21, desain 3-AI yang disepakati).

AI #1 Kurikulum: menyusun rencana per pertemuan dari nol, atau merapikan
kurikulum yang dimasukkan guru sendiri, berdasarkan info kelas (semua
opsional). Hasil generate adalah DRAF rencana — guru meninjau/mengedit,
menyimpan, lalu "terapkan" untuk membuat baris-baris Pertemuan beserta
potongan rencananya. Jalur manual tetap utuh: rencana bisa ditulis
tangan sepenuhnya tanpa AI.
"""

import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import get_subject, require_subject_manage
from ..ai_client import ProviderError, chat_completion
from ..db import get_db
from ..deps import require_csrf, require_roles
from ..models import Meeting, PedagogyTemplate, Subject, User
from ..pedagogi import can_access_template, ensure_preset_templates
from .generate import _resolve_setting

router = APIRouter(prefix="/api/v1/subjects", tags=["kurikulum"])
staff = require_roles("guru", "admin")


def _kelola(db: Session, user: User, subject_id: int) -> Subject:
    s = get_subject(db, subject_id)
    require_subject_manage(db, user, s)
    return s


def bersihkan_rencana(items) -> list[dict]:
    """Normalisasi daftar rencana per pertemuan (dari AI atau dari guru).
    Item tanpa judul dibuang; field dibatasi panjangnya."""
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Rencana harus berupa daftar pertemuan.")
    hasil = []
    for it in items[:60]:
        if not isinstance(it, dict):
            continue
        judul = str(it.get("judul") or "").strip()[:200]
        if not judul:
            continue
        hasil.append({
            "judul": judul,
            "tujuan": str(it.get("tujuan") or "").strip()[:500],
            "konsep": [str(k).strip()[:120] for k in (it.get("konsep") or []) if str(k).strip()][:12],
            "aktivitas": [str(a).strip()[:120] for a in (it.get("aktivitas") or []) if str(a).strip()][:8],
            "alur": (str(it["alur"]).strip()[:120] if it.get("alur") else None),
            "meeting_id": it.get("meeting_id") if isinstance(it.get("meeting_id"), int) else None,
        })
    if not hasil:
        raise HTTPException(status_code=400, detail="Rencana kosong — setiap pertemuan butuh judul.")
    return hasil


class GenerateKurikulumIn(BaseModel):
    mode: str = Field(pattern="^(nol|rapikan)$")
    jumlah_pertemuan: int = Field(ge=1, le=60)
    teks_kurikulum: Optional[str] = None
    ai_setting_id: Optional[int] = None


@router.post("/{subject_id}/kurikulum/generate", dependencies=[Depends(require_csrf)])
def generate_kurikulum(
    subject_id: int,
    body: GenerateKurikulumIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    s = _kelola(db, user, subject_id)
    if body.mode == "rapikan" and not (body.teks_kurikulum or "").strip():
        raise HTTPException(status_code=400, detail="Mode rapikan butuh teks kurikulum Anda.")
    ensure_preset_templates(db)
    templates = [
        t for t in db.query(PedagogyTemplate).all() if can_access_template(user, t)
    ]
    nama_alur = [t.nama for t in templates]
    setting = _resolve_setting(db, user, body.ai_setting_id)

    info = [f"Mata pelajaran/kelas: {s.nama}"]
    if s.jenjang:
        info.append(f"Jenjang/kelas: {s.jenjang}")
    if s.target_siswa:
        info.append(f"Target siswa: {s.target_siswa}")
    if s.tujuan_akhir:
        info.append(f"Tujuan akhir pembelajaran: {s.tujuan_akhir}")
    if s.deskripsi:
        info.append(f"Deskripsi kelas: {s.deskripsi}")
    info.append(f"Jumlah pertemuan: {body.jumlah_pertemuan}")

    system = (
        "Kamu adalah perancang kurikulum. Keluarkan HANYA JSON array (tanpa teks lain, "
        "tanpa fence) berisi tepat N objek pertemuan berurutan. Setiap objek:\n"
        '{"judul": str, "tujuan": str (1 kalimat), "konsep": [str, ...] (3-6 konsep kunci), '
        '"aktivitas": [str, ...] (2-4 aktivitas utama, mis. "studi kasus", "diskusi", "praktik"), '
        '"alur": str|null (nama alur mengajar yang paling cocok dari daftar yang diberikan, atau null)}.\n'
        "Susun agar pertemuan-pertemuan SALING BERKESINAMBUNGAN: konsep dibangun bertahap, "
        "kesulitan naik, dan variasikan aktivitas serta gaya antarpertemuan — jangan pola yang "
        "sama persis di semua pertemuan. Bahasa Indonesia."
    )
    if body.mode == "nol":
        user_prompt = (
            "Susun kurikulum dari nol berdasarkan info kelas berikut.\n\n"
            + "\n".join(info)
            + f"\n\nPilihan nama alur yang tersedia: {', '.join(nama_alur) or '-'}"
        )
    else:
        user_prompt = (
            "Rapikan kurikulum guru berikut ke dalam struktur per pertemuan. PERTAHANKAN isi, "
            "istilah, dan urutan asli guru sebisa mungkin; sesuaikan jumlahnya menjadi "
            f"{body.jumlah_pertemuan} pertemuan (gabung/pecah seperlunya secara wajar).\n\n"
            + "\n".join(info)
            + f"\n\nPilihan nama alur yang tersedia: {', '.join(nama_alur) or '-'}\n\n"
            + "KURIKULUM GURU:\n" + (body.teks_kurikulum or "")[:12000]
        )
    try:
        raw = chat_completion(
            setting,
            [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
        )
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    m = re.search(r"\[[\s\S]*\]", raw or "")
    if not m:
        raise HTTPException(status_code=502, detail="AI tidak mengembalikan rencana yang bisa dibaca. Coba lagi atau perjelas info kelas.")
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Rencana dari AI tidak valid (JSON rusak). Coba lagi.")
    rencana = bersihkan_rencana(items)
    # Alur hanya diterima bila cocok dengan template yang bisa diakses.
    for it in rencana:
        if it["alur"] and it["alur"] not in nama_alur:
            it["alur"] = None
    return {"rencana": rencana, "model": setting.model}


class SimpanKurikulumIn(BaseModel):
    pertemuan: list = Field(default_factory=list)


@router.put("/{subject_id}/kurikulum", dependencies=[Depends(require_csrf)])
def simpan_kurikulum(
    subject_id: int,
    body: SimpanKurikulumIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    s = _kelola(db, user, subject_id)
    s.kurikulum = bersihkan_rencana(body.pertemuan)
    db.commit()
    db.refresh(s)
    return {"kurikulum": s.kurikulum}


@router.post("/{subject_id}/kurikulum/terapkan", dependencies=[Depends(require_csrf)])
def terapkan_kurikulum(
    subject_id: int,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    """Buat baris Pertemuan dari rencana tersimpan. Item yang sudah punya
    meeting_id hanya diperbarui potongan rencananya (judul pertemuan yang
    sudah dibuat TIDAK ditimpa — guru mungkin sudah mengubahnya)."""
    s = _kelola(db, user, subject_id)
    if not s.kurikulum:
        raise HTTPException(status_code=400, detail="Kelas ini belum punya kurikulum tersimpan.")
    meetings = {
        m.id: m
        for m in db.query(Meeting).filter(Meeting.subject_id == s.id).all()
    }
    urutan_terakhir = max((m.urutan for m in meetings.values()), default=0)
    dibuat = 0
    rencana_baru = []
    for item in s.kurikulum:
        potongan = {k: v for k, v in item.items() if k != "meeting_id"}
        mid = item.get("meeting_id")
        if mid and mid in meetings:
            meetings[mid].rencana = potongan
            item_baru = {**item}
        else:
            urutan_terakhir += 1
            m = Meeting(
                subject_id=s.id,
                judul=item["judul"],
                urutan=urutan_terakhir,
                rencana=potongan,
            )
            db.add(m)
            db.flush()
            meetings[m.id] = m
            dibuat += 1
            item_baru = {**item, "meeting_id": m.id}
        rencana_baru.append(item_baru)
    s.kurikulum = rencana_baru
    db.commit()
    return {"dibuat": dibuat, "total": len(rencana_baru), "kurikulum": rencana_baru}
