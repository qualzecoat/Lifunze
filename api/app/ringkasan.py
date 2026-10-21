"""Ringkasan AKTUAL pertemuan — bahan kesinambungan generate (2026-10-21).

Dihitung deterministik dari materi & kuis yang BENAR-BENAR sudah ada di
pertemuan (bukan dari rencana): judul materi, sub-bab [HEADING], jumlah
soal sisipan, judul kuis. Tanpa panggilan AI — gratis dan selalu segar
karena dihitung saat dibutuhkan, lalu disimpan sebagai cache di
meetings.ringkasan.
"""

import re

from sqlalchemy.orm import Session

from .models import Material, Meeting, Quiz

_HEADING_RE = re.compile(r"\[HEADING\]([\s\S]*?)\[/HEADING\]")
_MAKS_KARAKTER = 1200


def hitung_ringkasan(db: Session, meeting: Meeting) -> str:
    materials = (
        db.query(Material).filter(Material.meeting_id == meeting.id).order_by(Material.id).all()
    )
    quizzes = db.query(Quiz).filter(Quiz.meeting_id == meeting.id).order_by(Quiz.id).all()
    if not materials and not quizzes:
        return ""
    baris = [f"Pertemuan '{meeting.judul}':"]
    for mt in materials:
        headings = [h.strip() for h in _HEADING_RE.findall(mt.teks_mentah or "") if h.strip()]
        jumlah_cek = (mt.teks_mentah or "").count("[CEK]")
        potongan = f"- Materi '{mt.judul}'"
        if headings:
            potongan += " — sub-bab: " + "; ".join(headings[:6])
        if jumlah_cek:
            potongan += f" ({jumlah_cek} soal sisipan)"
        baris.append(potongan)
    for q in quizzes:
        baris.append(f"- Kuis '{q.judul}' ({len(q.questions or [])} soal)")
    teks = "\n".join(baris)
    return teks[:_MAKS_KARAKTER]


def segarkan_ringkasan(db: Session, meeting: Meeting) -> str:
    """Hitung ulang + simpan ringkasan pertemuan (dipakai pembangun konteks
    generate). Mengembalikan teks ringkasannya."""
    teks = hitung_ringkasan(db, meeting)
    if teks != (meeting.ringkasan or ""):
        meeting.ringkasan = teks or None
        db.commit()
    return teks
