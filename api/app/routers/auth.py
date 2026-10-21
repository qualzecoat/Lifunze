"""Router autentikasi — SATU portal login untuk semua role.

Tidak ada endpoint registrasi publik (aturan terkunci Lifunze):
akun hanya dibuat lewat provisioning (admin/guru) atau seed admin.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    SESSION_DAYS,
    get_current_user,
    get_session_and_user,
    require_csrf,
)
from ..models import User, UserSession
from ..security import hash_password, new_csrf_token, new_session_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Throttle login (Fase 8): maks 5 kegagalan per (username, IP) dalam
# 10 menit, lalu terkunci 5 menit. In-memory — cukup untuk satu instance API.
# Audit #24: dulu kuncinya username saja — siapa pun bisa mengunci akun
# orang lain dari mana pun. Sekarang per pasangan username+IP, dan entri
# basi dibersihkan berkala agar dict tidak tumbuh tanpa batas.
import time as _time

_FAILED_LOGINS: dict[str, list[float]] = {}
_LOGIN_WINDOW = 600.0
_LOGIN_MAX_FAIL = 5
_LOGIN_LOCK = 300.0


def _kunci_throttle(username: str, request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = xff or (request.client.host if request.client else "?")
    return f"{username}|{ip}"


def _bersihkan_throttle(now: float) -> None:
    if len(_FAILED_LOGINS) < 1000:
        return
    for kunci in [k for k, v in _FAILED_LOGINS.items() if not v or now - v[-1] >= _LOGIN_WINDOW]:
        _FAILED_LOGINS.pop(kunci, None)


def _login_locked(kunci: str) -> bool:
    now = _time.time()
    _bersihkan_throttle(now)
    fails = [t for t in _FAILED_LOGINS.get(kunci, []) if now - t < _LOGIN_WINDOW]
    if fails:
        _FAILED_LOGINS[kunci] = fails
    else:
        _FAILED_LOGINS.pop(kunci, None)
    return len(fails) >= _LOGIN_MAX_FAIL and (now - fails[-1]) < _LOGIN_LOCK


def _record_login_fail(kunci: str) -> None:
    _FAILED_LOGINS.setdefault(kunci, []).append(_time.time())

MIN_PASSWORD = 8


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    new_password: str = Field(min_length=MIN_PASSWORD)


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=MIN_PASSWORD)


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nama_lengkap": user.nama_lengkap,
        "email": user.email,
        "role": user.role,
        "must_change_password": user.must_change_password,
    }


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    uname = body.username.strip()
    kunci = _kunci_throttle(uname.lower(), request)
    if _login_locked(kunci):
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan login gagal. Tunggu beberapa menit lalu coba lagi.",
        )
    user = (
        db.query(User)
        .filter(User.username == uname, User.deleted_at.is_(None))
        .first()
    )
    if user is None or not verify_password(body.password, user.password_hash):
        _record_login_fail(kunci)
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    _FAILED_LOGINS.pop(kunci, None)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan. Hubungi admin/guru Anda.")

    token = new_session_token()
    csrf = new_csrf_token()
    db.add(
        UserSession(
            id=token,
            user_id=user.id,
            csrf_token=csrf,
            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
        )
    )
    db.commit()

    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="lax",
        secure=settings.cookie_secure, max_age=SESSION_DAYS * 86400, path="/",
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, samesite="lax",
        secure=settings.cookie_secure, max_age=SESSION_DAYS * 86400, path="/",
    )
    return {"user": user_out(user), "csrf_token": csrf}


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    sess = db.get(UserSession, request.cookies.get(SESSION_COOKIE, ""))
    if sess is not None:
        db.delete(sess)
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


def _set_new_password(db: Session, request: Request, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    # Cabut sesi lain milik user ini (perangkat lain wajib login ulang).
    current = request.cookies.get(SESSION_COOKIE)
    db.query(UserSession).filter(
        UserSession.user_id == user.id, UserSession.id != current
    ).delete(synchronize_session=False)
    db.commit()


@router.post("/change-password", dependencies=[Depends(require_csrf)])
def change_password(
    body: ChangePasswordIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _, user = get_session_and_user(request, db)
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password lama salah.")
    _set_new_password(db, request, user, body.new_password)
    return {"ok": True}


@router.post("/first-login-password", dependencies=[Depends(require_csrf)])
def first_login_password(
    body: PasswordIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _, user = get_session_and_user(request, db)
    if not user.must_change_password:
        raise HTTPException(
            status_code=400,
            detail="Akun ini tidak sedang wajib ganti password. Gunakan menu Ganti Password.",
        )
    _set_new_password(db, request, user, body.new_password)
    return {"ok": True}
