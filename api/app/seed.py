"""Seed admin awal Lifunze — HANYA dari environment variable.

Aturan terkunci: akun admin tidak dibuat dari UI/API, hanya dari seed ini.
Jalankan:  python -m app.seed
Idempoten: bila sudah ada admin, tidak melakukan apa-apa.
Tanpa LIFUNZE_ADMIN_USERNAME/PASSWORD: berhenti dengan peringatan (tidak crash),
agar container tetap bisa jalan untuk keperluan lain.
"""

from .config import settings
from .db import SessionLocal
from .models import User
from .security import hash_password


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == "admin").first()
        if existing:
            print(f"Seed dilewati: admin sudah ada ({existing.username}).")
            return
        if not settings.admin_username or not settings.admin_password:
            print(
                "PERINGATAN: belum ada admin dan LIFUNZE_ADMIN_USERNAME/PASSWORD belum diatur. "
                "Atur kedua env itu lalu jalankan ulang: python -m app.seed"
            )
            return
        admin = User(
            username=settings.admin_username.strip(),
            nama_lengkap="Administrator",
            password_hash=hash_password(settings.admin_password),
            role="admin",
            created_by_id=None,
            must_change_password=False,
        )
        db.add(admin)
        db.commit()
        print(f"Admin awal dibuat: {admin.username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
