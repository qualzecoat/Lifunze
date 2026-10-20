"""Router subject, meeting & enrollment (Fase 2)."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import (
    get_meeting,
    get_subject,
    require_subject_manage,
    require_subject_view,
)
from ..db import get_db
from ..deps import get_current_user, require_csrf, require_roles
from ..models import Enrollment, Meeting, Subject, User
from ..deps import write_audit
from ..provisioning import create_user_record, user_admin_out

router = APIRouter(prefix="/api/v1/subjects", tags=["subjects"])
staff = require_roles("guru", "admin")


# ------------------------------------------------------------------ helpers
def subject_out(db: Session, s: Subject) -> dict:
    return {
        "id": s.id,
        "nama": s.nama,
        "deskripsi": s.deskripsi,
        "dibuat_oleh": s.dibuat_oleh,
        "is_archived": s.is_archived,
        "jumlah_pertemuan": db.query(Meeting).filter(Meeting.subject_id == s.id).count(),
        "jumlah_siswa": db.query(Enrollment).filter(Enrollment.subject_id == s.id).count(),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def meeting_out(db: Session, m: Meeting) -> dict:
    from ..models import Material, Quiz

    materials = (
        db.query(Material).filter(Material.meeting_id == m.id).order_by(Material.id).all()
    )
    quizzes = db.query(Quiz).filter(Quiz.meeting_id == m.id).order_by(Quiz.id).all()
    # Flag "sudah di bank" dari penanda asal milik pemilik kelas (paket 2026-10-20).
    from ..models import SavedMaterial, SavedQuiz

    pemilik = db.get(Subject, m.subject_id)
    pemilik_id = pemilik.dibuat_oleh if pemilik else None
    materi_di_bank = {
        s.asal_id
        for s in db.query(SavedMaterial).filter(
            SavedMaterial.dibuat_oleh == pemilik_id, SavedMaterial.asal_id.isnot(None)
        )
    }
    kuis_di_bank = {
        s.asal_id
        for s in db.query(SavedQuiz).filter(
            SavedQuiz.dibuat_oleh == pemilik_id, SavedQuiz.asal_id.isnot(None)
        )
    }
    return {
        "id": m.id,
        "subject_id": m.subject_id,
        "judul": m.judul,
        "urutan": m.urutan,
        "tanggal": m.tanggal.isoformat() if m.tanggal else None,
        "deskripsi": m.deskripsi,
        "materials": [
            {
                "id": mt.id,
                "judul": mt.judul,
                "jumlah_file": len(mt.files),
                "di_bank": mt.id in materi_di_bank,
                "grup_dokumen": mt.grup_dokumen,
                "jenis": mt.jenis,
                "created_at": mt.created_at.isoformat() if mt.created_at else None,
            }
            for mt in materials
        ],
        "quizzes": [
            {
                "id": q.id,
                "judul": q.judul,
                "tipe": q.tipe,
                "jumlah_soal": len(q.questions),
                "di_bank": q.id in kuis_di_bank,
                "grup_dokumen": q.grup_dokumen,
                "jenis": q.jenis,
            }
            for q in quizzes
        ],
        "jumlah_kuis": len(quizzes),
    }


# ------------------------------------------------------------------ subjects
class SubjectIn(BaseModel):
    nama: str = Field(min_length=1, max_length=200)
    deskripsi: Optional[str] = None


@router.get("")
def list_subjects(
    termasuk_arsip: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == "admin":
        q = db.query(Subject)
    elif user.role == "guru":
        q = db.query(Subject).filter(Subject.dibuat_oleh == user.id)
    else:  # siswa: yang diikuti
        q = (
            db.query(Subject)
            .join(Enrollment, Enrollment.subject_id == Subject.id)
            .filter(Enrollment.student_id == user.id)
        )
    if not termasuk_arsip or user.role == "siswa":
        q = q.filter(Subject.is_archived.is_(False))
    return [subject_out(db, s) for s in q.order_by(Subject.nama).all()]


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_subject(body: SubjectIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = Subject(nama=body.nama.strip(), deskripsi=body.deskripsi, dibuat_oleh=user.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return subject_out(db, s)


@router.get("/{subject_id}")
def get_subject_detail(subject_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = get_subject(db, subject_id)
    require_subject_view(db, user, s)
    meetings = (
        db.query(Meeting).filter(Meeting.subject_id == s.id).order_by(Meeting.urutan).all()
    )
    out = subject_out(db, s)
    out["meetings"] = [meeting_out(db, m) for m in meetings]
    out["bisa_kelola"] = user.role == "admin" or (user.role == "guru" and s.dibuat_oleh == user.id)
    return out


class SubjectPatchIn(BaseModel):
    nama: Optional[str] = Field(default=None, min_length=1, max_length=200)
    deskripsi: Optional[str] = None
    is_archived: Optional[bool] = None


@router.patch("/{subject_id}", dependencies=[Depends(require_csrf)])
def update_subject(
    subject_id: int,
    body: SubjectPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_subject(db, subject_id)
    require_subject_manage(db, user, s)
    if body.nama is not None:
        s.nama = body.nama.strip()
    if body.deskripsi is not None:
        s.deskripsi = body.deskripsi
    if body.is_archived is not None:
        s.is_archived = body.is_archived
    db.commit()
    db.refresh(s)
    return subject_out(db, s)


@router.delete("/{subject_id}", dependencies=[Depends(require_csrf)])
def delete_subject(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_subject(db, subject_id)
    require_subject_manage(db, user, s)
    db.query(Enrollment).filter(Enrollment.subject_id == s.id).delete(synchronize_session=False)
    db.delete(s)  # cascade ORM: meetings -> materials/quizzes ikut terhapus
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ meetings
class MeetingIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    tanggal: Optional[date] = None
    deskripsi: Optional[str] = None


@router.post("/{subject_id}/meetings", status_code=201, dependencies=[Depends(require_csrf)])
def create_meeting(
    subject_id: int,
    body: MeetingIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_subject(db, subject_id)
    require_subject_manage(db, user, s)
    last = (
        db.query(Meeting)
        .filter(Meeting.subject_id == s.id)
        .order_by(Meeting.urutan.desc())
        .first()
    )
    m = Meeting(
        subject_id=s.id,
        judul=body.judul.strip(),
        urutan=(last.urutan + 1) if last else 1,
        tanggal=body.tanggal,
        deskripsi=body.deskripsi,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return meeting_out(db, m)


class ReorderIn(BaseModel):
    urutan: list[int]  # daftar meeting_id sesuai urutan baru (lengkap)


@router.post("/{subject_id}/meetings/reorder", dependencies=[Depends(require_csrf)])
def reorder_meetings(
    subject_id: int,
    body: ReorderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_subject(db, subject_id)
    require_subject_manage(db, user, s)
    meetings = db.query(Meeting).filter(Meeting.subject_id == s.id).all()
    by_id = {m.id: m for m in meetings}
    if set(body.urutan) != set(by_id.keys()):
        raise HTTPException(status_code=400, detail="Daftar urutan harus memuat semua pertemuan kelas ini.")
    for i, mid in enumerate(body.urutan, start=1):
        by_id[mid].urutan = i
    db.commit()
    return [meeting_out(db, by_id[mid]) for mid in body.urutan]


@router.patch("/meetings/{meeting_id}", dependencies=[Depends(require_csrf)])
def update_meeting(
    meeting_id: int,
    body: MeetingIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_meeting(db, meeting_id)
    s = get_subject(db, m.subject_id)
    require_subject_manage(db, user, s)
    m.judul = body.judul.strip()
    m.tanggal = body.tanggal
    m.deskripsi = body.deskripsi
    db.commit()
    db.refresh(m)
    return meeting_out(db, m)


@router.delete("/meetings/{meeting_id}", dependencies=[Depends(require_csrf)])
def delete_meeting(
    meeting_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_meeting(db, meeting_id)
    s = get_subject(db, m.subject_id)
    require_subject_manage(db, user, s)
    db.delete(m)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- enrollment
class EnrollIn(BaseModel):
    siswa_ids: list[int]


@router.get("/{subject_id}/students")
def list_subject_students(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_subject(db, subject_id)
    require_subject_view(db, user, s)
    rows = (
        db.query(User)
        .join(Enrollment, Enrollment.student_id == User.id)
        .filter(Enrollment.subject_id == s.id)
        .order_by(User.username)
        .all()
    )
    return [
        {"id": u.id, "username": u.username, "nama_lengkap": u.nama_lengkap, "is_active": u.is_active}
        for u in rows
    ]


@router.post("/{subject_id}/enroll", dependencies=[Depends(require_csrf)])
def enroll_students(
    subject_id: int,
    body: EnrollIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_subject(db, subject_id)
    require_subject_manage(db, user, s)
    ditambahkan, dilewati = 0, []
    seen: set[int] = set()
    for sid in body.siswa_ids:
        if sid in seen:
            dilewati.append({"siswa_id": sid, "pesan": "Duplikat dalam daftar yang sama."})
            continue
        seen.add(sid)
        siswa = db.get(User, sid)
        if siswa is None or siswa.role != "siswa" or siswa.deleted_at is not None:
            dilewati.append({"siswa_id": sid, "pesan": "Akun siswa tidak ditemukan."})
            continue
        if not siswa.is_active:
            dilewati.append({"siswa_id": sid, "pesan": "Akun siswa nonaktif."})
            continue
        exists = (
            db.query(Enrollment)
            .filter(Enrollment.student_id == sid, Enrollment.subject_id == s.id)
            .first()
        )
        if exists:
            dilewati.append({"siswa_id": sid, "pesan": "Sudah terdaftar di kelas ini."})
            continue
        db.add(Enrollment(student_id=sid, subject_id=s.id, enrolled_by=user.id))
        ditambahkan += 1
    db.commit()
    return {"ditambahkan": ditambahkan, "dilewati": dilewati}


@router.delete("/{subject_id}/enroll/{siswa_id}", dependencies=[Depends(require_csrf)])
def unenroll_student(
    subject_id: int,
    siswa_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_subject(db, subject_id)
    require_subject_manage(db, user, s)
    row = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == siswa_id, Enrollment.subject_id == s.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Siswa tidak terdaftar di kelas ini.")
    db.delete(row)
    db.commit()
    return {"ok": True}


class NewStudentIn(BaseModel):
    username: str
    nama_lengkap: Optional[str] = None
    password: str


@router.post("/{subject_id}/students/create", status_code=201, dependencies=[Depends(require_csrf)])
def create_student_in_subject(
    subject_id: int,
    body: NewStudentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """U5 (audit UX): buat akun siswa BARU dan langsung daftarkan ke kelas ini
    dalam satu langkah — guru tidak perlu bolak-balik halaman Siswa."""
    s = get_subject(db, subject_id)
    require_subject_manage(db, user, s)
    siswa = create_user_record(db, user, body.username, body.nama_lengkap, body.password, "siswa")
    write_audit(db, user.id, "user.create", "user", siswa.id, {"role": "siswa", "username": siswa.username, "via": "kelas"})
    db.add(Enrollment(student_id=siswa.id, subject_id=s.id))
    db.commit()
    db.refresh(siswa)
    return {**user_admin_out(db, siswa), "terdaftar_di_kelas": s.id}
