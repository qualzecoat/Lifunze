"""Test Fase 1: auth, provisioning + created_by, import CSV, pengaturan AI."""

import pytest
from conftest import login, make_user

from app.db import SessionLocal
from app.models import AiSetting, User
from app.security import decrypt_secret


# --------------------------------------------------------------------- auth
def test_seed_admin_bisa_login(client):
    from app.seed import main as seed_main

    seed_main()  # admin dari env conftest
    csrf = login(client, "admin", "admin-rahasia-123")
    assert csrf
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    seed_main()  # idempoten — tidak membuat admin kedua
    db = SessionLocal()
    assert db.query(User).filter(User.role == "admin").count() == 1
    db.close()


def test_login_password_salah(client):
    make_user("guru1", "guru")
    res = client.post("/api/v1/auth/login", json={"username": "guru1", "password": "salah"})
    assert res.status_code == 401


def test_me_tanpa_login_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_mencabut_sesi(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    res = client.post("/api/v1/auth/logout", headers={"x-csrf-token": csrf})
    assert res.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_mutasi_tanpa_csrf_ditolak(client):
    make_user("admin1", "admin")
    login(client, "admin1")
    res = client.post(
        "/api/v1/admin/teachers",
        json={"username": "guru1", "nama_lengkap": "Guru Satu", "password": "password123"},
    )
    assert res.status_code == 403  # CSRF


def test_first_login_password_flow(client):
    admin_id = make_user("admin1", "admin")
    csrf_admin = login(client, "admin1")
    res = client.post(
        "/api/v1/admin/teachers",
        json={"username": "guru1", "nama_lengkap": "Guru Satu", "password": "sementara123"},
        headers={"x-csrf-token": csrf_admin},
    )
    assert res.status_code == 201
    assert res.json()["must_change_password"] is True
    assert res.json()["dibuat_oleh"]["username"] == "admin1"

    client2 = client
    csrf = login(client2, "guru1", "sementara123")
    res = client2.post(
        "/api/v1/auth/first-login-password",
        json={"new_password": "baru-kuat-456"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    assert client2.get("/api/v1/auth/me").json()["must_change_password"] is False
    # password lama mati, baru hidup
    from fastapi.testclient import TestClient
    from app.main import app

    c3 = TestClient(app)
    assert c3.post("/api/v1/auth/login", json={"username": "guru1", "password": "sementara123"}).status_code == 401
    login(c3, "guru1", "baru-kuat-456")


# ------------------------------------------------------------- provisioning
def test_guru_hanya_kelola_siswa_buatannya(client):
    make_user("admin1", "admin")
    g1 = make_user("guru1", "guru")
    make_user("guru2", "guru")
    csrf1 = login(client, "guru1")
    res = client.post(
        "/api/v1/users/students",
        json={"username": "siswa1", "nama_lengkap": "Siswa Satu", "password": "password123"},
        headers={"x-csrf-token": csrf1},
    )
    assert res.status_code == 201
    siswa_id = res.json()["id"]
    assert res.json()["dibuat_oleh"]["username"] == "guru1"

    # guru2: daftar siswanya kosong & tidak bisa mengubah siswa guru1
    from fastapi.testclient import TestClient
    from app.main import app

    c2 = TestClient(app)
    csrf2 = login(c2, "guru2")
    assert c2.get("/api/v1/users/students").json() == []
    res = c2.patch(
        f"/api/v1/users/students/{siswa_id}",
        json={"is_active": False},
        headers={"x-csrf-token": csrf2},
    )
    assert res.status_code == 403

    # guru1 bisa me-reset password siswanya
    res = client.patch(
        f"/api/v1/users/students/{siswa_id}",
        json={"new_password": "resetpass123"},
        headers={"x-csrf-token": csrf1},
    )
    assert res.status_code == 200
    assert res.json()["must_change_password"] is True


def test_siswa_tidak_bisa_provisioning_atau_ai(client):
    guru_id = make_user("guru1", "guru")
    make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "siswa1")
    assert (
        client.post(
            "/api/v1/users/students",
            json={"username": "x", "password": "password123"},
            headers={"x-csrf-token": csrf},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/ai/settings").status_code == 403
    assert client.get("/api/v1/admin/users").status_code == 403


def test_import_csv_dengan_baris_gagal(client):
    make_user("guru1", "guru")
    make_user("sudahada", "siswa")
    csrf = login(client, "guru1")
    csv_text = (
        "username,nama_lengkap,password\n"
        "andi,Andi Wijaya,password123\n"
        "sudahada,Duplikat,password123\n"
        "budi,,password123\n"
    )
    res = client.post(
        "/api/v1/users/students/import",
        files={"file": ("siswa.csv", csv_text, "text/csv")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["berhasil"] == 2  # andi + budi (savepoint: duplikat tidak membatalkan yang lain)
    assert len(body["gagal"]) == 1
    daftar = client.get("/api/v1/users/students").json()
    assert {s["username"] for s in daftar} == {"andi", "budi"}


def test_soft_delete_user(client):
    make_user("admin1", "admin")
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "admin1")
    res = client.delete(f"/api/v1/admin/users/{siswa_id}", headers={"x-csrf-token": csrf})
    assert res.status_code == 200
    # hilang dari daftar & tidak bisa login
    users = client.get("/api/v1/admin/users").json()
    assert all(u["username"] != "siswa1" for u in users)
    from fastapi.testclient import TestClient
    from app.main import app

    c2 = TestClient(app)
    assert c2.post("/api/v1/auth/login", json={"username": "siswa1", "password": "password123"}).status_code == 401
    # admin tidak bisa dihapus
    admin2_id = make_user("admin2", "admin")
    res = client.delete(f"/api/v1/admin/users/{admin2_id}", headers={"x-csrf-token": csrf})
    assert res.status_code == 400


# ------------------------------------------------------------ pengaturan AI
class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, headers=None):
        assert url.endswith("/models")
        return FakeResponse(200, {"data": [{"id": "model-b"}, {"id": "model-a"}]})

    def post(self, url, headers=None, json=None):
        assert url.endswith("/chat/completions")
        assert json["model"] == "model-a"
        return FakeResponse(200, {"choices": []})


@pytest.fixture()
def fake_http(monkeypatch):
    monkeypatch.setattr("app.routers.ai_settings.http_client", lambda: FakeClient())
    # Provider dipalsukan total di tes ini -> pemeriksaan resolve SSRF
    # (audit #12) ikut dipalsukan; pagarnya sendiri dites di test_audit_c.
    monkeypatch.setattr("app.routers.ai_settings.assert_public_target", lambda url: None)


def test_ai_settings_crud_dan_enkripsi(client, fake_http):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    res = client.post(
        "/api/v1/ai/settings",
        json={
            "nama": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1/",
            "api_key": "sk-rahasia-123456",
            "is_default": True,
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["base_url"] == "https://openrouter.ai/api/v1"  # trailing slash dibersihkan
    assert body["api_key_masked"] == "sk-••••56"
    assert "sk-rahasia-123456" not in str(body)

    # di DB tersimpan terenkripsi & bisa didekripsi kembali
    db = SessionLocal()
    row = db.query(AiSetting).first()
    assert row.api_key_encrypted != "sk-rahasia-123456"
    assert decrypt_secret(row.api_key_encrypted) == "sk-rahasia-123456"
    setting_id = row.id
    db.close()

    # fetch models (fake) & tes koneksi (fake)
    res = client.post(
        "/api/v1/ai/settings/fetch-models",
        json={"base_url": "https://openrouter.ai/api/v1", "api_key": "sk-x"},
        headers={"x-csrf-token": csrf},
    )
    assert res.json()["models"] == ["model-a", "model-b"]

    res = client.patch(
        f"/api/v1/ai/settings/{setting_id}",
        json={"model": "model-a"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    res = client.post(
        f"/api/v1/ai/settings/{setting_id}/test", headers={"x-csrf-token": csrf}
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # guru lain tidak bisa melihat setting ini
    make_user("guru2", "guru")
    from fastapi.testclient import TestClient
    from app.main import app

    c2 = TestClient(app)
    csrf2 = login(c2, "guru2")
    assert c2.get("/api/v1/ai/settings").json() == []
    assert (
        c2.patch(
            f"/api/v1/ai/settings/{setting_id}",
            json={"nama": "bajak"},
            headers={"x-csrf-token": csrf2},
        ).status_code
        == 404
    )
