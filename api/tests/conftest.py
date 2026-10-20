"""Fixture pengujian Lifunze — DB SQLite sementara, skema dibuat ulang per test."""

import os
import tempfile

# Env HARUS diatur sebelum app.* diimpor (settings dibaca saat import).
os.environ["LIFUNZE_DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.mkdtemp(prefix="lifunze-test-"), "test.db"
)
os.environ["LIFUNZE_ADMIN_USERNAME"] = "admin"
os.environ["LIFUNZE_ADMIN_PASSWORD"] = "admin-rahasia-123"

from cryptography.fernet import Fernet  # noqa: E402

os.environ["LIFUNZE_FERNET_KEY"] = Fernet.generate_key().decode()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401 — daftarkan tabel
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def make_user(username, role, password="password123", created_by_id=None, must_change=False):
    db = SessionLocal()
    try:
        u = User(
            username=username,
            nama_lengkap=username.title(),
            password_hash=hash_password(password),
            role=role,
            created_by_id=created_by_id,
            must_change_password=must_change,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def login(client: TestClient, username: str, password: str = "password123") -> str:
    """Login dan kembalikan csrf_token."""
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["csrf_token"]
