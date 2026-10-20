"""Router admin — kelola guru & semua user.

Hanya role admin. Akun admin sendiri TIDAK bisa dibuat/dihapus dari sini
(admin hanya via seed env).
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_csrf, require_roles, write_audit
from ..models import User, UserSession
from ..provisioning import create_user_record, user_admin_out
from ..security import hash_password

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
admin_only = require_roles("admin")


class TeacherIn(BaseModel):
    username: str
    nama_lengkap: Optional[str] = None
    password: str = Field(min_length=8)


class UserPatchIn(BaseModel):
    is_active: Optional[bool] = None
    new_password: Optional[str] = Field(default=None, min_length=8)


@router.post("/teachers", status_code=201, dependencies=[Depends(require_csrf)])
def create_teacher(
    body: TeacherIn,
    actor: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    guru = create_user_record(db, actor, body.username, body.nama_lengkap, body.password, "guru")
    write_audit(db, actor.id, "user.create", "user", guru.id, {"role": "guru", "username": guru.username})
    db.commit()
    db.refresh(guru)
    return user_admin_out(db, guru)


@router.get("/users")
def list_users(
    role: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    q = db.query(User).filter(User.deleted_at.is_(None))
    if role:
        q = q.filter(User.role == role)
    if search:
        like = f"%{search}%"
        q = q.filter((User.username.ilike(like)) | (User.nama_lengkap.ilike(like)))
    users = q.order_by(User.role, User.username).all()
    return [user_admin_out(db, u) for u in users]


def _get_target(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    return user


@router.patch("/users/{user_id}", dependencies=[Depends(require_csrf)])
def patch_user(
    user_id: int,
    body: UserPatchIn,
    actor: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    target = _get_target(db, user_id)
    changed = {}
    if body.is_active is not None:
        if target.id == actor.id and body.is_active is False:
            raise HTTPException(status_code=400, detail="Tidak bisa menonaktifkan akun sendiri.")
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


@router.delete("/users/{user_id}", dependencies=[Depends(require_csrf)])
def delete_user(
    user_id: int,
    actor: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    target = _get_target(db, user_id)
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="Akun admin tidak dapat dihapus.")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus akun sendiri.")
    target.is_active = False
    target.deleted_at = datetime.now(timezone.utc)
    db.query(UserSession).filter(UserSession.user_id == target.id).delete(synchronize_session=False)
    write_audit(db, actor.id, "user.delete", "user", target.id, {"username": target.username, "role": target.role})
    db.commit()
    return {"ok": True, "pesan": f"Akun {target.username} dihapus (soft-delete)."}
