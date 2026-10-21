"""Tes Batch 1 Pedagogi (2026-10-21): template alur mengajar merujuk
paket, preset sistem, mutasi owner-only (D1), fork, berbagi, dan
penyaringan spec oleh template."""

from tests.conftest import login, make_user

BAGIAN = [
    {"peran": "pembuka", "label": "Pembuka", "status": "wajib", "modul": ["inti-materi"], "catatan": "Satu pemicu."},
    {"peran": "konsep", "label": "Konsep", "status": "wajib", "modul": ["inti-materi", "tabel-data"], "catatan": ""},
    {"peran": "cek", "label": "Cek", "status": "opsional", "modul": ["cek-pemahaman"], "catatan": ""},
]


def test_preset_template_tersedia_dan_tidak_bisa_diubah(client):
    make_user("guru_ped", "guru")
    csrf = login(client, "guru_ped")
    r = client.get("/api/v1/templates")
    assert r.status_code == 200, r.text
    data = r.json()
    nama_preset = {t["nama"] for t in data["preset"]}
    assert {"Konsep Bertahap", "Berbasis Kasus", "Praktik Langsung", "Eksplorasi Masalah"} <= nama_preset
    preset = data["preset"][0]
    assert preset["preset"] is True and preset["pemilik"] == "Sistem"
    assert preset["bagian"], "preset harus punya bagian"
    # Preset tidak bisa diubah/dihapus — fork dulu.
    r = client.patch(
        f"/api/v1/templates/{preset['id']}",
        json={"nama": "Diubah", "bagian": []},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 403
    r = client.delete(f"/api/v1/templates/{preset['id']}", headers={"x-csrf-token": csrf})
    assert r.status_code == 403
    # Fork berhasil menjadi milik guru dan bisa diubah.
    r = client.post(f"/api/v1/templates/{preset['id']}/fork", headers={"x-csrf-token": csrf})
    assert r.status_code == 201, r.text
    fork = r.json()
    assert fork["milik_saya"] is True and fork["nama"].endswith("(Fork)")
    r = client.patch(
        f"/api/v1/templates/{fork['id']}",
        json={"nama": "Alur Saya", "bagian": BAGIAN},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200 and r.json()["nama"] == "Alur Saya"


def test_template_crud_owner_only_dan_berbagi(client):
    make_user("guru_t1", "guru")
    make_user("guru_t2", "guru")
    csrf = login(client, "guru_t1")
    r = client.post(
        "/api/v1/templates",
        json={"nama": "Alur Rahasia", "bagian": BAGIAN},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["visibilitas"] == "private"

    # Guru lain tidak melihat template privat.
    login(client, "guru_t2")
    assert client.get(f"/api/v1/templates/{t['id']}").status_code == 404
    data = client.get("/api/v1/templates").json()
    assert all(x["id"] != t["id"] for x in data["dibagikan"])

    # Pemilik membagikan -> muncul di daftar dibagikan guru lain.
    csrf = login(client, "guru_t1")
    r = client.put(
        f"/api/v1/templates/{t['id']}/share",
        json={"mode": "shared"},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200
    csrf2 = login(client, "guru_t2")
    data = client.get("/api/v1/templates").json()
    assert any(x["id"] == t["id"] for x in data["dibagikan"])
    # ...tetap tidak bisa mengubah milik orang (D1).
    r = client.patch(
        f"/api/v1/templates/{t['id']}",
        json={"nama": "Bajakan", "bagian": []},
        headers={"x-csrf-token": csrf2},
    )
    assert r.status_code == 403
    # Bagian tidak sah ditolak.
    csrf = login(client, "guru_t1")
    r = client.post(
        "/api/v1/templates",
        json={"nama": "Rusak", "bagian": [{"peran": "ngawur"}]},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 400


def test_preview_spec_tersaring_oleh_template(client):
    make_user("guru_spec", "guru")
    csrf = login(client, "guru_spec")
    # Template hanya memakai modul inti-materi -> spec tidak memuat modul
    # latihan/proyek/kuis (penyaringan bekerja), tapi memuat inti-materi.
    r = client.post(
        "/api/v1/templates/preview-spec",
        json={"bagian": [BAGIAN[0]], "paket_dasar": True},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200, r.text
    spec = r.json()["spec"]
    assert "Modul:" in spec
    assert r.json()["pack_nama"] == "Kelas Lengkap"
    # Bandingkan: tanpa bagian (tidak menyaring) spec jauh lebih panjang.
    r2 = client.post(
        "/api/v1/templates/preview-spec",
        json={"bagian": [], "paket_dasar": True},
        headers={"x-csrf-token": csrf},
    )
    assert r2.status_code == 200
    assert len(spec) < len(r2.json()["spec"])
