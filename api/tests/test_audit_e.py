"""Tes keputusan produk D1–D3 dari audit 2026-10-21 (diputuskan &
dikerjakan 2026-10-21 atas lampu hijau Qualze "lanjut garap selanjutnya"):

- D1: mutasi paket parser owner-only; admin hanya membaca.
- D2: kelas arsip tertutup untuk siswa (pengelola tetap bisa membuka).
- D3: tenggat Tugas lunak — pengumpulan terlambat diterima + ditandai.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login, make_user

PROYEK = "[PROJECT]\n[TITLE]Poster[/TITLE]\n[DESCRIPTION]Buat poster.[/DESCRIPTION]\n[/PROJECT]"
MATERI = "[MATERIAL]\n[TITLE]M[/TITLE]\n[PARAGRAPH]Isi.[/PARAGRAPH]\n[/MATERIAL]"


def _kelas(client, csrf, nama="Kelas E"):
    sid = client.post(
        "/api/v1/subjects", json={"nama": nama}, headers={"x-csrf-token": csrf}
    ).json()["id"]
    mid = client.post(
        f"/api/v1/subjects/{sid}/meetings",
        json={"judul": "Pertemuan 1"},
        headers={"x-csrf-token": csrf},
    ).json()["id"]
    return sid, mid


def test_d1_admin_tidak_bisa_mengubah_paket_guru_lain(client):
    make_user("guru_pemilik", "guru")
    make_user("admin_satu", "admin")
    csrf = login(client, "guru_pemilik")
    pack = client.post(
        "/api/v1/packs",
        json={"nama": "Paket Milik Guru", "module_slugs": ["inti-materi"]},
        headers={"x-csrf-token": csrf},
    ).json()

    # Admin bisa MELIHAT paketnya (akses baca untuk pengawasan)...
    csrf_admin = login(client, "admin_satu")
    r = client.get(f"/api/v1/packs/{pack['id']}")
    assert r.status_code == 200, r.text
    # ...tapi tidak mengubah, membagikan, atau menghapusnya.
    r = client.patch(
        f"/api/v1/packs/{pack['id']}",
        json={"nama": "Diambil Alih", "module_slugs": ["inti-materi"]},
        headers={"x-csrf-token": csrf_admin},
    )
    assert r.status_code == 403, r.text
    r = client.put(
        f"/api/v1/packs/{pack['id']}/share",
        json={"mode": "all", "user_ids": []},
        headers={"x-csrf-token": csrf_admin},
    )
    assert r.status_code == 403, r.text
    r = client.delete(
        f"/api/v1/packs/{pack['id']}", headers={"x-csrf-token": csrf_admin}
    )
    assert r.status_code == 403, r.text
    # Pemilik tetap bebas mengubah paketnya sendiri.
    csrf = login(client, "guru_pemilik")
    r = client.patch(
        f"/api/v1/packs/{pack['id']}",
        json={"nama": "Paket Milik Guru v2", "module_slugs": ["inti-materi"]},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200, r.text


def test_d2_kelas_arsip_tertutup_untuk_siswa(client):
    guru_id = make_user("guru_arsip", "guru")
    siswa_id = make_user("siswa_arsip", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru_arsip")
    sid, mid = _kelas(client, csrf)
    mat = client.post(
        f"/api/v1/meetings/{mid}/materials",
        json={"judul": "Materi", "teks_mentah": MATERI},
        headers={"x-csrf-token": csrf},
    ).json()
    client.post(
        f"/api/v1/subjects/{sid}/enroll",
        json={"siswa_ids": [siswa_id]},
        headers={"x-csrf-token": csrf},
    )

    c = TestClient(app)
    login(c, "siswa_arsip")
    assert c.get(f"/api/v1/subjects/{sid}").status_code == 200
    assert c.get(f"/api/v1/materials/{mat['id']}").status_code == 200

    # Arsipkan → akses siswa tertutup di detail kelas & materi.
    r = client.patch(
        f"/api/v1/subjects/{sid}",
        json={"is_archived": True},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200, r.text
    r = c.get(f"/api/v1/subjects/{sid}")
    assert r.status_code == 403
    assert "diarsipkan" in r.json()["detail"]
    assert c.get(f"/api/v1/materials/{mat['id']}").status_code == 403

    # Guru pemilik tetap bisa membuka kelas arsipnya.
    assert client.get(f"/api/v1/subjects/{sid}").status_code == 200

    # Batalkan arsip → siswa bisa masuk lagi.
    client.patch(
        f"/api/v1/subjects/{sid}",
        json={"is_archived": False},
        headers={"x-csrf-token": csrf},
    )
    assert c.get(f"/api/v1/subjects/{sid}").status_code == 200


def _atur_tenggat(material_id: int, kapan: datetime) -> None:
    from app.db import SessionLocal
    from app.models import Material

    db = SessionLocal()
    try:
        m = db.get(Material, material_id)
        m.jenis = "tugas"
        m.tenggat = kapan
        db.commit()
    finally:
        db.close()


def test_d3_tenggat_lunak_ditandai_terlambat(client):
    guru_id = make_user("guru_tenggat", "guru")
    siswa_id = make_user("siswa_tenggat", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru_tenggat")
    sid, mid = _kelas(client, csrf)
    client.post(
        f"/api/v1/subjects/{sid}/enroll",
        json={"siswa_ids": [siswa_id]},
        headers={"x-csrf-token": csrf},
    )

    def buat_proyek(judul):
        return client.post(
            f"/api/v1/meetings/{mid}/materials",
            json={"judul": judul, "teks_mentah": PROYEK},
            headers={"x-csrf-token": csrf},
        ).json()

    lewat = buat_proyek("Tugas Lewat")
    _atur_tenggat(lewat["id"], datetime.now(timezone.utc) - timedelta(days=1))
    tepat = buat_proyek("Tugas Tepat")
    _atur_tenggat(tepat["id"], datetime.now(timezone.utc) + timedelta(days=1))

    c = TestClient(app)
    csrf_s = login(c, "siswa_tenggat")
    # Lewat tenggat: TETAP diterima (201), tapi ditandai terlambat.
    r = c.post(
        f"/api/v1/materials/{lewat['id']}/submissions",
        files={"file": ("telat.txt", b"isi telat", "text/plain")},
        headers={"x-csrf-token": csrf_s},
    )
    assert r.status_code == 201, r.text
    assert r.json()["terlambat"] is True
    # Sebelum tenggat: tidak ditandai.
    r = c.post(
        f"/api/v1/materials/{tepat['id']}/submissions",
        files={"file": ("tepat.txt", b"isi tepat", "text/plain")},
        headers={"x-csrf-token": csrf_s},
    )
    assert r.status_code == 201, r.text
    assert r.json()["terlambat"] is False
    # Daftar guru memuat penanda yang sama.
    rows = client.get(f"/api/v1/materials/{lewat['id']}/submissions").json()
    assert rows["submissions"][0]["terlambat"] is True
