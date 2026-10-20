"""Test Fase 8: hardening — health, header keamanan, magic bytes, throttle
login, dan validasi konfigurasi production."""

from conftest import login, make_user

from app.config import Settings, validate_production

MATERI = "[MATERIAL]\n[TITLE]Bab[/TITLE]\nIsi.\n[/MATERIAL]"


def test_health_dan_header_keamanan(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and body["db"] == "ok"
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "SAMEORIGIN"


def test_magic_bytes_upload(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    sid = client.post("/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf}).json()["id"]
    mat = client.post(
        f"/api/v1/meetings/{mid}/materials",
        json={"judul": "M", "teks_mentah": MATERI},
        headers={"x-csrf-token": csrf},
    ).json()

    # teks biasa diganti nama jadi .png -> ditolak magic bytes
    res = client.post(
        f"/api/v1/materials/{mat['id']}/files",
        files={"file": ("palsu.png", b"ini cuma teks", "image/png")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400
    assert "magic" in res.json()["detail"]

    # PDF asli (header benar) -> diterima
    res = client.post(
        f"/api/v1/materials/{mat['id']}/files",
        files={"file": ("dok.pdf", b"%PDF-1.4 isi dokumen", "application/pdf")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201

    # .sb3 adalah ZIP -> header PK; header salah -> ditolak
    res = client.post(
        f"/api/v1/materials/{mat['id']}/files",
        files={"file": ("proyek.sb3", b"bukan zip", "application/octet-stream")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400


def test_throttle_login(client):
    make_user("korban", "guru")
    for _ in range(5):
        res = client.post("/api/v1/auth/login", json={"username": "korban", "password": "salah"})
        assert res.status_code == 401
    # percobaan ke-6 (bahkan password BENAR) terkunci sementara
    res = client.post("/api/v1/auth/login", json={"username": "korban", "password": "password123"})
    assert res.status_code == 429
    # username lain tidak ikut terkunci
    make_user("aman", "guru")
    res = client.post("/api/v1/auth/login", json={"username": "aman", "password": "password123"})
    assert res.status_code == 200


def test_validasi_production():
    assert validate_production(Settings(env="dev")) == []

    lemah = Settings(env="production")
    problems = validate_production(lemah)
    # (Di konteks test, FERNET key terisi dari conftest; sisanya tetap bermasalah.)
    assert len(problems) >= 3
    assert any("COOKIE_SECURE" in p for p in problems)
    assert any("PostgreSQL" in p for p in problems)

    kuat = Settings(
        env="production",
        fernet_key="kunci-fernet-valid",
        secret_key="x" * 32,
        cookie_secure=True,
        database_url="postgresql+psycopg://u:p@db:5432/lifunze",
        admin_username="admin",
        admin_password="password-admin-kuat",
    )
    assert validate_production(kuat) == []
