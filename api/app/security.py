"""Utilitas keamanan Lifunze: hashing password (argon2), enkripsi API key
(Fernet), dan pembuatan token sesi.

API key AI user TIDAK PERNAH disimpan plaintext dan tidak pernah
dikembalikan utuh oleh API — hanya bentuk mask yang boleh tampil.
"""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from .config import settings

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def _fernet() -> Fernet:
    key = settings.fernet_key.strip()
    if not key:
        raise RuntimeError(
            "LIFUNZE_FERNET_KEY belum diatur — wajib untuk menyimpan API key AI. "
            "Generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise RuntimeError("API key tersimpan tidak bisa didekripsi (FERNET_KEY berubah?).")


def mask_secret(plain: str) -> str:
    """Bentuk tampil aman: 3 char awal + mask + 2 char akhir."""
    if not plain:
        return ""
    if len(plain) <= 6:
        return "••••"
    return f"{plain[:3]}••••{plain[-2:]}"


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
