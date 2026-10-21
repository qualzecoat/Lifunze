"""Kontrol akses berbasis subject (Fase 2+).

Aturan:
- admin: akses penuh ke semua subject.
- guru: mengelola subject miliknya (dibuat_oleh = dia); melihat hanya miliknya.
- siswa: melihat subject yang ia ikuti (enrollment) saja.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Enrollment, Material, Meeting, Subject, User


def get_subject(db: Session, subject_id: int) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Mata pelajaran tidak ditemukan.")
    return subject


def get_meeting(db: Session, meeting_id: int) -> Meeting:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Pertemuan tidak ditemukan.")
    return meeting


def get_material(db: Session, material_id: int) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Materi tidak ditemukan.")
    return material


def is_enrolled(db: Session, siswa_id: int, subject_id: int) -> bool:
    return (
        db.query(Enrollment)
        .filter(Enrollment.student_id == siswa_id, Enrollment.subject_id == subject_id)
        .first()
        is not None
    )


def can_manage_subject(user: User, subject: Subject) -> bool:
    return user.role == "admin" or (user.role == "guru" and subject.dibuat_oleh == user.id)


def require_subject_view(db: Session, user: User, subject: Subject) -> None:
    if can_manage_subject(user, subject):
        return
    # Keputusan produk D2 (2026-10-21, dari audit): kelas yang diarsipkan
    # TERTUTUP untuk siswa — bukan hanya hilang dari daftar. Pengelola
    # (guru pemilik/admin) tetap bisa membuka untuk mengelola atau
    # mengeluarkan kelas dari arsip.
    if subject.is_archived:
        raise HTTPException(
            status_code=403,
            detail="Kelas ini sudah diarsipkan dan tidak dapat diakses lagi. Hubungi guru Anda bila ini keliru.",
        )
    if user.role == "siswa" and is_enrolled(db, user.id, subject.id):
        return
    raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke mata pelajaran ini.")


def require_subject_manage(db: Session, user: User, subject: Subject) -> None:
    if not can_manage_subject(user, subject):
        raise HTTPException(status_code=403, detail="Hanya pemilik mata pelajaran / admin yang dapat mengubahnya.")
