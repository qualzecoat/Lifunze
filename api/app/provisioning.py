"""Logika provisioning akun — dipakai router admin & siswa.

Aturan terkunci:
- Siswa hanya dibuat guru/admin; guru hanya dibuat admin; admin hanya via seed.
- Setiap akun mencatat created_by_id (NULL hanya untuk admin seed).
- Password awal selalu sementara: must_change_password = True.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import User
from .security import hash_password


def ensure_unique_username(db: Session, username: str) -> str:
    username = username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username wajib diisi.")
    exists = db.query(User).filter(User.username == username).first()
    if exists is not None:
        raise HTTPException(status_code=400, detail=f"Username '{username}' sudah digunakan.")
    return username


def create_user_record(
    db: Session,
    actor: User,
    username: str,
    nama_lengkap: str | None,
    password: str,
    role: str,
) -> User:
    username = ensure_unique_username(db, username)
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password awal minimal 8 karakter.")
    user = User(
        username=username,
        nama_lengkap=(nama_lengkap or "").strip() or None,
        password_hash=hash_password(password),
        role=role,
        created_by_id=actor.id,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    return user


def creator_summary(db: Session, user: User) -> dict | None:
    if user.created_by_id is None:
        return None
    creator = db.get(User, user.created_by_id)
    if creator is None:
        return None
    return {"id": creator.id, "username": creator.username, "role": creator.role}


def user_admin_out(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nama_lengkap": user.nama_lengkap,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "dibuat_oleh": creator_summary(db, user),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
