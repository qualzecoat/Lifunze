"""Router siswa — provisioning oleh guru/admin.

Guru hanya melihat & mengelola siswa yang IA buat (created_by = dirinya);
admin melihat semua siswa.
"""

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_csrf, require_roles, write_audit
from ..models import User, UserSession
from ..provisioning import create_user_record, user_admin_out
from ..security import hash_password

router = APIRouter(prefix="/api/v1/users", tags=["users"])
guru_admin = require_roles("guru", "admin")


class StudentIn(BaseModel):
    username: str
    nama_lengkap: Optional[str] = None
    password: str = Field(min_length=8)


class StudentPatchIn(BaseModel):
    is_active: Optional[bool] = None
    new_password: Optional[str] = Field(default=None, min_length=8)


@router.post("/students", status_code=201, dependencies=[Depends(require_csrf)])
def create_student(
    body: StudentIn,
    actor: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    siswa = create_user_record(db, actor, body.username, body.nama_lengkap, body.password, "siswa")
    write_audit(db, actor.id, "user.create", "user", siswa.id, {"role": "siswa", "username": siswa.username})
    db.commit()
    db.refresh(siswa)
    return user_admin_out(db, siswa)


@router.post("/students/import", dependencies=[Depends(require_csrf)])
async def import_students(
    file: UploadFile = File(...),
    subject_id: Optional[int] = Form(default=None),
    actor: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    """Import massal siswa dari CSV. Kolom: username,nama_lengkap,password
    (nama_lengkap boleh kosong). Baris yang gagal tidak menggagalkan baris lain.
    Bila subject_id diberikan, siswa yang berhasil dibuat langsung didaftarkan
    ke kelas itu (U5 audit UX) — aktor wajib pengelola kelasnya."""
    target_subject = None
    if subject_id is not None:
        from ..access import get_subject, require_subject_manage

        target_subject = get_subject(db, subject_id)
        require_subject_manage(db, actor, target_subject)
    # Audit #27: baca terbatas + batas jumlah baris (tiap baris = hash
    # password Argon2 yang mahal; CSV raksasa = DoS CPU).
    from ..uploads import read_upload_limited

    raw = await read_upload_limited(file, 2 * 1024 * 1024)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File harus teks CSV (UTF-8).")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "username" not in reader.fieldnames or "password" not in reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="Header CSV wajib memuat kolom username dan password (nama_lengkap opsional).",
        )
    baris = list(reader)
    if len(baris) > 1000:
        raise HTTPException(
            status_code=400,
            detail=f"CSV berisi {len(baris)} baris — batas maksimum 1000 baris per impor. Bagi file menjadi beberapa impor.",
        )

    berhasil, gagal = 0, []
    for i, row in enumerate(baris, start=2):  # baris 1 = header
        username = (row.get("username") or "").strip()
        password = (row.get("password") or "").strip()
        nama = (row.get("nama_lengkap") or "").strip()
        try:
            # SAVEPOINT per baris: kegagalan satu baris tidak membatalkan baris lain.
            with db.begin_nested():
                siswa = create_user_record(db, actor, username, nama or None, password, "siswa")
                if target_subject is not None:
                    from ..models import Enrollment

                    db.add(Enrollment(student_id=siswa.id, subject_id=target_subject.id))
            berhasil += 1
        except HTTPException as e:
            gagal.append({"baris": i, "username": username, "pesan": e.detail})
        except Exception:
            gagal.append({"baris": i, "username": username, "pesan": "Gagal membuat akun baris ini."})
    write_audit(db, actor.id, "user.import", "user", None, {"berhasil": berhasil, "gagal": len(gagal)})
    db.commit()
    return {"total": berhasil + len(gagal), "berhasil": berhasil, "gagal": gagal}


@router.get("/students")
def list_students(
    actor: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    q = db.query(User).filter(User.role == "siswa", User.deleted_at.is_(None))
    if actor.role == "guru":
        q = q.filter(User.created_by_id == actor.id)
    students = q.order_by(User.username).all()
    return [user_admin_out(db, s) for s in students]


def _get_manageable_student(db: Session, actor: User, student_id: int) -> User:
    target = db.get(User, student_id)
    if target is None or target.role != "siswa" or target.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan.")
    if actor.role == "guru" and target.created_by_id != actor.id:
        raise HTTPException(status_code=403, detail="Siswa ini bukan buatan Anda.")
    return target


@router.patch("/students/{student_id}", dependencies=[Depends(require_csrf)])
def patch_student(
    student_id: int,
    body: StudentPatchIn,
    actor: User = Depends(guru_admin),
    db: Session = Depends(get_db),
):
    target = _get_manageable_student(db, actor, student_id)
    changed = {}
    if body.is_active is not None:
        target.is_active = body.is_active
        changed["is_active"] = body.is_active
    if body.new_password:
        target.password_hash = hash_password(body.new_password)
        target.must_change_password = True
        changed["password_reset"] = True
        db.query(UserSession).filter(UserSession.user_id == target.id).delete(synchronize_session=False)
    if changed:
        write_audit(db, actor.id, "user.update", "user", target.id, changed)
        db.commit()
        db.refresh(target)
    return user_admin_out(db, target)
