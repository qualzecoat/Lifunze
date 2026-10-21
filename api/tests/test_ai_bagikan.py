"""Distribusi Pengaturan AI oleh admin (2026-10-21): admin membagikan
koneksinya per API key dengan mode semua / whitelist / blacklist.
Pengaturan bersama menjadi default CADANGAN bagi guru yang belum punya
pengaturan sendiri; milik sendiri selalu didahulukan; kunci admin tidak
pernah terekspos ke penerima."""

from tests.conftest import login, make_user
from tests.test_fase5 import MATERI_OK as MATERI_SAH
from tests.test_generate_pedagogi import buat_paket_lengkap, fake_ai


def buat_admin(client, csrf, mode="semua", targets=None, model="model-admin"):
    res = client.post(
        "/api/v1/ai/settings",
        json={
            "nama": "Kunci Sekolah",
            "base_url": "https://api.contoh.id/v1",
            "api_key": "sk-rahasia-admin-123456",
            "model": model,
            "is_default": True,
            "dibagikan_mode": mode,
            "target_ids": targets or [],
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    return res.json()


def fake_ai_setting(monkeypatch, responses, seen):
    """Seperti fake_ai tetapi mencatat SETTING yang dipakai generate."""
    queue = list(responses)

    def _fake(setting, messages, temperature=0.7):
        seen.append(setting)
        assert queue, "fake AI kehabisan jawaban"
        return queue.pop(0)

    monkeypatch.setattr("app.routers.generate.chat_completion", _fake)


def generate_materi(client, csrf, pack_id, setting_id=None):
    body = {"kind": "materi", "pack_id": pack_id, "brief": {"topik": "Pecahan"}}
    if setting_id is not None:
        body["ai_setting_id"] = setting_id
    return client.post("/api/v1/generate", json=body, headers={"x-csrf-token": csrf})


def test_mode_semua_jadi_cadangan_guru(client, monkeypatch):
    admin_id = make_user("admin_ai", "admin")
    make_user("guru_polos", "guru")
    csrf_a = login(client, "admin_ai")
    dibagikan = buat_admin(client, csrf_a, mode="semua")
    assert dibagikan["dibagikan_mode"] == "semua"

    csrf_g = login(client, "guru_polos")
    daftar = client.get("/api/v1/ai/settings").json()
    bersama = [s for s in daftar if not s["milik_saya"]]
    assert len(bersama) == 1
    assert bersama[0]["pemilik"] is not None
    assert bersama[0]["api_key_masked"] is None  # kunci admin tidak terekspos

    pack = buat_paket_lengkap(client, csrf_g)
    seen = []
    fake_ai_setting(monkeypatch, [MATERI_SAH], seen)
    res = generate_materi(client, csrf_g, pack["id"])
    assert res.status_code == 201, res.text
    # Generate memakai kunci admin.
    assert seen[0].id == dibagikan["id"]


def test_whitelist_dan_blacklist(client, monkeypatch):
    make_user("admin_ai2", "admin")
    id_b = make_user("guru_b", "guru")
    make_user("guru_c", "guru")
    csrf_a = login(client, "admin_ai2")
    putih = buat_admin(client, csrf_a, mode="whitelist", targets=[id_b], model="model-putih")

    # Guru C tidak termasuk whitelist: daftar kosong + generate ditolak.
    csrf_c = login(client, "guru_c")
    assert [s for s in client.get("/api/v1/ai/settings").json() if not s["milik_saya"]] == []
    pack_c = buat_paket_lengkap(client, csrf_c)
    fake_ai(monkeypatch, [MATERI_SAH])
    assert generate_materi(client, csrf_c, pack_c["id"]).status_code == 400
    assert generate_materi(client, csrf_c, pack_c["id"], setting_id=putih["id"]).status_code == 404

    # Blacklist: ganti mode — guru B dikecualikan, guru C boleh.
    csrf_a = login(client, "admin_ai2")  # sesi TestClient sempat berpindah ke guru
    r = client.patch(
        f"/api/v1/ai/settings/{putih['id']}",
        json={"dibagikan_mode": "blacklist", "target_ids": [id_b]},
        headers={"x-csrf-token": csrf_a},
    )
    assert r.status_code == 200, r.text
    csrf_b = login(client, "guru_b")
    assert [s for s in client.get("/api/v1/ai/settings").json() if not s["milik_saya"]] == []
    csrf_c2 = login(client, "guru_c")
    assert len([s for s in client.get("/api/v1/ai/settings").json() if not s["milik_saya"]]) == 1


def test_milik_sendiri_didahulukan_dan_nonadmin_ditolak(client, monkeypatch):
    make_user("admin_ai3", "admin")
    make_user("guru_punya", "guru")
    csrf_a = login(client, "admin_ai3")
    buat_admin(client, csrf_a, mode="semua")

    csrf_g = login(client, "guru_punya")
    sendiri = client.post(
        "/api/v1/ai/settings",
        json={
            "nama": "Kunci Sendiri",
            "base_url": "https://api.contoh.id/v1",
            "api_key": "sk-kunci-sendiri-999",
            "model": "model-sendiri",
            "is_default": True,
        },
        headers={"x-csrf-token": csrf_g},
    )
    assert sendiri.status_code == 201, sendiri.text

    pack = buat_paket_lengkap(client, csrf_g)
    seen = []
    fake_ai_setting(monkeypatch, [MATERI_SAH], seen)
    res = generate_materi(client, csrf_g, pack["id"])
    assert res.status_code == 201, res.text
    assert seen[0].model == "model-sendiri"  # bukan model-admin

    # Guru BUKAN admin tidak boleh membagikan pengaturannya.
    tolak = client.post(
        "/api/v1/ai/settings",
        json={
            "nama": "Nekat",
            "base_url": "https://api.contoh.id/v1",
            "api_key": "sk-xxx-111",
            "dibagikan_mode": "semua",
        },
        headers={"x-csrf-token": csrf_g},
    )
    assert tolak.status_code == 400
    # Endpoint recipients khusus admin.
    assert client.get("/api/v1/ai/settings/recipients").status_code == 403
