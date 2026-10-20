"""Dependency autentikasi, RBAC, CSRF, dan audit log Lifunze."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuditLog, User, UserSession

SESSION_COOKIE = "lifunze_session"
CSRF_COOKIE = "lifunze_csrf"
SESSION_DAYS = 7


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_session_and_user(request: Request, db: Session) -> tuple[UserSession, User]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Belum login.")
    sess = db.get(UserSession, token)
    if sess is None or _as_utc(sess.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sesi berakhir. Silakan login lagi.")
    user = db.get(User, sess.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Akun tidak ditemukan.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan. Hubungi admin/guru Anda.")
    return sess, user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_session_and_user(request, db)[1]


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke fitur ini.")
        return user

    return checker


def require_csrf(request: Request, db: Session = Depends(get_db)) -> None:
    """CSRF double-submit: header X-CSRF-Token harus sama dengan token di sesi."""
    sess, _ = get_session_and_user(request, db)
    header = request.headers.get("x-csrf-token")
    if not header or header != sess.csrf_token:
        raise HTTPException(status_code=403, detail="Token CSRF tidak valid.")


def write_audit(
    db: Session,
    actor_id: Optional[int],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    meta: Optional[dict] = None,
) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, meta=meta))
