"""Router Pengalaman Belajar (Fase 6).

Pengumuman per mapel, notifikasi pengguna, progress belajar (materi dibaca +
kuis dikerjakan), dan tugas file untuk materi [PROJECT] dengan penilaian
rubrik. Skema: announcements, notifications, material_reads, submissions.
"""

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import (
    get_material,
    get_meeting,
    get_subject,
    require_subject_manage,
    require_subject_view,
)
from ..config import settings
from ..db import get_db
from ..deps import get_current_user, require_csrf
from ..models import (
    Announcement,
    Enrollment,
    Material,
    MaterialRead,
    Notification,
    Quiz,
    QuizAttempt,
    Submission,
    User,
)
from ..notify import notify
from .materials import _storage_path

router = APIRouter(tags=["learning"])

SUBMISSION_EXT = {".png", ".jpg", ".jpeg", ".pdf", ".mp4", ".zip", ".txt", ".sb3"}
MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".zip": "application/zip",
    ".txt": "text/plain",
    ".sb3": "application/octet-stream",
}


def _enrolled_ids(db: Session, subject_id: int) -> list[int]:
    rows = db.query(Enrollment).filter(Enrollment.subject_id == subject_id).all()
    return [r.student_id for r in rows]


def _subject_of_material(db: Session, material: Material):
    meeting = get_meeting(db, material.meeting_id)
    return get_subject(db, meeting.subject_id), meeting


# --------------------------------------------------------------- pengumuman
class AnnouncementIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    isi: str = Field(min_length=1)


def _announcement_out(a: Announcement, db: Session) -> dict:
    author = db.get(User, a.dibuat_oleh)
    return {
        "id": a.id,
        "subject_id": a.subject_id,
        "judul": a.judul,
        "isi": a.isi,
        "dibuat_oleh": a.dibuat_oleh,
        "penulis": (author.nama_lengkap or author.username) if author else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/api/v1/subjects/{subject_id}/announcements")
def list_announcements(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = get_subject(db, subject_id)
    require_subject_view(db, user, subject)
    rows = (
        db.query(Announcement)
        .filter(Announcement.subject_id == subject.id)
        .order_by(Announcement.id.desc())
        .all()
    )
    return [_announcement_out(a, db) for a in rows]


@router.post("/api/v1/subjects/{subject_id}/announcements", status_code=201, dependencies=[Depends(require_csrf)])
def create_announcement(
    subject_id: int,
    body: AnnouncementIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = get_subject(db, subject_id)
    require_subject_manage(db, user, subject)
    a = Announcement(
        subject_id=subject.id,
        dibuat_oleh=user.id,
        judul=body.judul.strip(),
        isi=body.isi.strip(),
    )
    db.add(a)
    db.flush()
    notify(
        db,
        _enrolled_ids(db, subject.id),
        "pengumuman",
        {"subject_id": subject.id, "announcement_id": a.id, "judul": a.judul, "kelas": subject.nama},
    )
    db.commit()
    db.refresh(a)
    return _announcement_out(a, db)


@router.delete("/api/v1/announcements/{announcement_id}", dependencies=[Depends(require_csrf)])
def delete_announcement(
    announcement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = db.get(Announcement, announcement_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Pengumuman tidak ditemukan.")
    subject = get_subject(db, a.subject_id)
    require_subject_manage(db, user, subject)
    db.delete(a)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------- notifikasi
def _notification_out(n: Notification) -> dict:
    return {
        "id": n.id,
        "tipe": n.tipe,
        "payload": n.payload or {},
        "sudah_dibaca": n.read_at is not None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("/api/v1/notifications")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .limit(30)
        .all()
    )
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .count()
    )
    return {"items": [_notification_out(n) for n in rows], "belum_dibaca": unread}


@router.get("/api/v1/notifications/summary")
def notification_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .count()
    )
    return {"belum_dibaca": unread}


@router.post("/api/v1/notifications/read-all", dependencies=[Depends(require_csrf)])
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .update({Notification.read_at: now}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True}


@router.post("/api/v1/notifications/{notification_id}/read", dependencies=[Depends(require_csrf)])
def mark_one_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan.")
    n.read_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ progress
@router.post("/api/v1/materials/{material_id}/read", dependencies=[Depends(require_csrf)])
def mark_material_read(
    material_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "siswa":
        raise HTTPException(status_code=403, detail="Hanya siswa yang menandai materi dibaca.")
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_view(db, user, subject)
    existing = (
        db.query(MaterialRead)
        .filter(MaterialRead.material_id == m.id, MaterialRead.siswa_id == user.id)
        .first()
    )
    if existing is None:
        db.add(MaterialRead(material_id=m.id, siswa_id=user.id))
        db.commit()
    return {"ok": True, "sudah_dibaca": True}


def _progress_for_siswa(db: Session, subject, siswa_id: int) -> dict:
    meetings = sorted(subject.meetings, key=lambda x: x.urutan)
    read_ids = {
        r.material_id
        for r in db.query(MaterialRead)
        .filter(MaterialRead.siswa_id == siswa_id)
        .all()
    }
    attempt_by_quiz = {
        a.quiz_id: a
        for a in db.query(QuizAttempt).filter(QuizAttempt.siswa_id == siswa_id).all()
    }
    total_materi = 0
    total_dibaca = 0
    total_kuis = 0
    total_dikerjakan = 0
    skor_list: list[float] = []
    per_meeting = []
    for mt in meetings:
        materials = db.query(Material).filter(Material.meeting_id == mt.id).all()
        quizzes = db.query(Quiz).filter(Quiz.meeting_id == mt.id).all()
        m_items = []
        for m in materials:
            total_materi += 1
            dibaca = m.id in read_ids
            total_dibaca += 1 if dibaca else 0
            m_items.append({"id": m.id, "judul": m.judul, "dibaca": dibaca})
        q_items = []
        for q in quizzes:
            total_kuis += 1
            att = attempt_by_quiz.get(q.id)
            selesai = att is not None and att.status in ("submitted", "graded")
            total_dikerjakan += 1 if selesai else 0
            if att is not None and att.skor is not None:
                skor_list.append(att.skor)
            q_items.append(
                {
                    "id": q.id,
                    "judul": q.judul,
                    "status_attempt": att.status if att else None,
                    "skor": att.skor if att else None,
                }
            )
        per_meeting.append(
            {"meeting_id": mt.id, "judul": mt.judul, "materials": m_items, "quizzes": q_items}
        )
    persen_materi = round(100 * total_dibaca / total_materi, 1) if total_materi else 100.0
    persen_kuis = round(100 * total_dikerjakan / total_kuis, 1) if total_kuis else 100.0
    total_item = total_materi + total_kuis
    total_selesai = total_dibaca + total_dikerjakan
    return {
        "pertemuan": per_meeting,
        "ringkasan": {
            "total_materi": total_materi,
            "materi_dibaca": total_dibaca,
            "total_kuis": total_kuis,
            "kuis_dikerjakan": total_dikerjakan,
            "persen_materi": persen_materi,
            "persen_kuis": persen_kuis,
            "persen_total": round(100 * total_selesai / total_item, 1) if total_item else 100.0,
            "rata_skor": round(sum(skor_list) / len(skor_list), 1) if skor_list else None,
        },
    }


@router.get("/api/v1/subjects/{subject_id}/progress")
def subject_progress(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = get_subject(db, subject_id)
    require_subject_view(db, user, subject)
    if user.role == "siswa":
        return {"mode": "siswa", **_progress_for_siswa(db, subject, user.id)}
    # mode guru/admin: ringkasan per siswa terdaftar
    rows = []
    for sid in _enrolled_ids(db, subject.id):
        siswa = db.get(User, sid)
        ringkasan = _progress_for_siswa(db, subject, sid)["ringkasan"]
        rows.append(
            {
                "siswa": {
                    "id": siswa.id,
                    "username": siswa.username,
                    "nama_lengkap": siswa.nama_lengkap,
                }
                if siswa
                else None,
                **ringkasan,
            }
        )
    return {"mode": "guru", "per_siswa": rows}


# ------------------------------------------------------- tugas file [PROJECT]
def _is_project(material: Material) -> bool:
    return re.search(r"^\s*\[PROJECT\]", material.teks_mentah or "", re.MULTILINE) is not None


def _submission_out(db: Session, s: Submission) -> dict:
    siswa = db.get(User, s.siswa_id)
    filename = os.path.basename(s.storage_key)
    display = filename.split("_", 1)[1] if "_" in filename else filename
    return {
        "id": s.id,
        "material_id": s.material_id,
        "siswa": (
            {"id": siswa.id, "username": siswa.username, "nama_lengkap": siswa.nama_lengkap}
            if siswa
            else None
        ),
        "nama_file": display,
        "catatan": s.catatan,
        "skor": s.skor,
        "feedback_rubrik": s.feedback_rubrik,
        "dinilai_oleh": s.dinilai_oleh,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.post("/api/v1/materials/{material_id}/submissions", status_code=201, dependencies=[Depends(require_csrf)])
async def upload_submission(
    material_id: int,
    file: UploadFile = File(...),
    catatan: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "siswa":
        raise HTTPException(status_code=403, detail="Hanya siswa yang mengumpulkan tugas.")
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_view(db, user, subject)
    if not _is_project(m):
        raise HTTPException(
            status_code=400,
            detail="Materi ini bukan tugas proyek [PROJECT]; pengumpulan file tidak tersedia.",
        )
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUBMISSION_EXT:
        raise HTTPException(
            status_code=400,
            detail="Format file tidak didukung. Gunakan PNG, JPG, PDF, MP4, ZIP, TXT, atau SB3 (Scratch).",
        )
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Ukuran file melebihi {settings.max_upload_mb} MB.")

    safe_name = os.path.basename(file.filename or f"tugas{ext}").replace("/", "_")
    storage_key = f"submissions/{m.id}/{uuid.uuid4().hex}_{safe_name}"
    path = _storage_path(storage_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as out:
        out.write(content)

    existing = (
        db.query(Submission)
        .filter(Submission.material_id == m.id, Submission.siswa_id == user.id)
        .first()
    )
    if existing is not None:
        old_path = _storage_path(existing.storage_key)
        if os.path.exists(old_path):
            os.remove(old_path)
        existing.storage_key = storage_key
        existing.catatan = catatan
        existing.skor = None
        existing.feedback_rubrik = None
        existing.dinilai_oleh = None
        db.commit()
        db.refresh(existing)
        return _submission_out(db, existing)

    s = Submission(material_id=m.id, siswa_id=user.id, storage_key=storage_key, catatan=catatan)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _submission_out(db, s)


@router.get("/api/v1/materials/{material_id}/submissions")
def list_submissions(
    material_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_view(db, user, subject)
    q = db.query(Submission).filter(Submission.material_id == m.id)
    if user.role == "siswa":
        q = q.filter(Submission.siswa_id == user.id)
    rows = q.order_by(Submission.id.desc()).all()
    return {
        "is_project": _is_project(m),
        "submissions": [_submission_out(db, s) for s in rows],
    }


@router.get("/api/v1/submissions/{submission_id}/download")
def download_submission(
    submission_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(Submission, submission_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Submission tidak ditemukan.")
    m = get_material(db, s.material_id)
    subject, _ = _subject_of_material(db, m)
    if user.id != s.siswa_id:
        require_subject_manage(db, user, subject)
    path = _storage_path(s.storage_key)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan di penyimpanan.")
    ext = os.path.splitext(s.storage_key)[1].lower()
    return FileResponse(
        path,
        media_type=MIME_BY_EXT.get(ext, "application/octet-stream"),
        filename=os.path.basename(s.storage_key),
    )


class GradeSubmissionIn(BaseModel):
    skor: float = Field(ge=0, le=100)
    feedback_rubrik: dict = Field(default_factory=dict)


@router.post("/api/v1/submissions/{submission_id}/grade", dependencies=[Depends(require_csrf)])
def grade_submission(
    submission_id: int,
    body: GradeSubmissionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(Submission, submission_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Submission tidak ditemukan.")
    m = get_material(db, s.material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_manage(db, user, subject)
    s.skor = body.skor
    s.feedback_rubrik = body.feedback_rubrik
    s.dinilai_oleh = user.id
    notify(
        db,
        [s.siswa_id],
        "nilai_keluar",
        {"material_id": m.id, "submission_id": s.id, "judul": m.judul, "skor": body.skor, "kelas": subject.nama},
    )
    db.commit()
    db.refresh(s)
    return _submission_out(db, s)
