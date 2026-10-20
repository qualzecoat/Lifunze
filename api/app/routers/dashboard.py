"""Router Dashboard (U4 audit UX).

Dashboard menjawab pertanyaan utama penggunanya:
- guru/admin: "apa yang harus kukerjakan sekarang?" -> antrean perlu dinilai
  (esai & tugas proyek), kelas saya, aktivitas/notifikasi terbaru.
- siswa: kelas saya + progress masing-masing.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import (
    Enrollment,
    Material,
    Meeting,
    Notification,
    Quiz,
    QuizAttempt,
    Subject,
    Submission,
    User,
)
from .learning import _notification_out, _progress_for_siswa

router = APIRouter(tags=["dashboard"])


def _managed_subjects(db: Session, user: User):
    q = db.query(Subject).filter(Subject.is_archived.is_(False))
    if user.role == "guru":
        q = q.filter(Subject.dibuat_oleh == user.id)
    return q.order_by(Subject.id).all()


@router.get("/api/v1/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .count()
    )
    aktivitas = [
        _notification_out(n)
        for n in db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .limit(5)
        .all()
    ]

    if user.role == "siswa":
        kelas = []
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == user.id).all()
        for e in enrollments:
            subject = db.get(Subject, e.subject_id)
            if subject is None or subject.is_archived:
                continue
            ringkasan = _progress_for_siswa(db, subject, user.id)["ringkasan"]
            kelas.append(
                {
                    "id": subject.id,
                    "nama": subject.nama,
                    "persen_total": ringkasan["persen_total"],
                    "materi_dibaca": ringkasan["materi_dibaca"],
                    "total_materi": ringkasan["total_materi"],
                    "kuis_dikerjakan": ringkasan["kuis_dikerjakan"],
                    "total_kuis": ringkasan["total_kuis"],
                    "rata_skor": ringkasan["rata_skor"],
                }
            )
        return {
            "mode": "siswa",
            "kelas": kelas,
            "aktivitas": aktivitas,
            "notifikasi_belum_dibaca": unread,
        }

    subjects = _managed_subjects(db, user)
    subject_ids = [s.id for s in subjects]
    kelas_saya = [
        {
            "id": s.id,
            "nama": s.nama,
            "jumlah_siswa": db.query(Enrollment).filter(Enrollment.subject_id == s.id).count(),
            "jumlah_pertemuan": db.query(Meeting).filter(Meeting.subject_id == s.id).count(),
        }
        for s in subjects
    ]

    # Esai menunggu dinilai: attempt terkumpul (submitted) yang belum punya skor.
    esai_rows = []
    if subject_ids:
        rows = (
            db.query(Quiz, func.count(QuizAttempt.id))
            .join(Meeting, Quiz.meeting_id == Meeting.id)
            .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
            .filter(
                Meeting.subject_id.in_(subject_ids),
                QuizAttempt.status == "submitted",
                QuizAttempt.skor.is_(None),
            )
            .group_by(Quiz.id)
            .all()
        )
        subject_by_id = {s.id: s for s in subjects}
        for quiz, jumlah in rows:
            meeting = db.get(Meeting, quiz.meeting_id)
            subj = subject_by_id.get(meeting.subject_id) if meeting else None
            esai_rows.append(
                {
                    "quiz_id": quiz.id,
                    "judul": quiz.judul,
                    "subject_id": meeting.subject_id if meeting else None,
                    "kelas": subj.nama if subj else None,
                    "jumlah": jumlah,
                }
            )

    # Tugas proyek menunggu dinilai: submission tanpa skor.
    tugas_rows = []
    if subject_ids:
        rows = (
            db.query(Material, func.count(Submission.id))
            .join(Meeting, Material.meeting_id == Meeting.id)
            .join(Submission, Submission.material_id == Material.id)
            .filter(Meeting.subject_id.in_(subject_ids), Submission.skor.is_(None))
            .group_by(Material.id)
            .all()
        )
        subject_by_id = {s.id: s for s in subjects}
        for material, jumlah in rows:
            meeting = db.get(Meeting, material.meeting_id)
            subj = subject_by_id.get(meeting.subject_id) if meeting else None
            tugas_rows.append(
                {
                    "material_id": material.id,
                    "judul": material.judul,
                    "subject_id": meeting.subject_id if meeting else None,
                    "kelas": subj.nama if subj else None,
                    "jumlah": jumlah,
                }
            )

    return {
        "mode": "guru",
        "perlu_dinilai": {"esai": esai_rows, "tugas": tugas_rows},
        "kelas_saya": kelas_saya,
        "aktivitas": aktivitas,
        "notifikasi_belum_dibaca": unread,
    }
