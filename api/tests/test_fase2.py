"""Test Fase 2: subject/meeting/enrollment, materi TCML, lampiran, bank."""

from conftest import login, make_user
from fastapi.testclient import TestClient

from app.main import app

VALID_MATERIAL = """[MATERIAL]
[TITLE]Pecahan Dasar[/TITLE]
[PARAGRAPH]Pecahan adalah bagian dari keseluruhan.[/PARAGRAPH]
[/MATERIAL]"""

INVALID_MATERIAL = """[MATERIAL]
[TITLE]Tidak ditutup
[/MATERIAL]"""

VALID_QUIZ_PG = """[QUIZ]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]1 + 1 = ?[/QUESTION]
[OPTIONS]
A. 1
B. 2
C. 3
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""


def second_client():
    return TestClient(app)


def buat_kelas(client, csrf, nama="Matematika"):
    res = client.post(
        "/api/v1/subjects",
        json={"nama": nama, "deskripsi": "Kelas uji"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def buat_pertemuan(client, csrf, subject_id, judul="Pertemuan 1"):
    res = client.post(
        f"/api/v1/subjects/{subject_id}/meetings",
        json={"judul": judul},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    return res.json()


# ------------------------------------------------------------------- subjects
def test_subject_crud_dan_kepemilikan(client):
    make_user("guru1", "guru")
    make_user("guru2", "guru")
    csrf = login(client, "guru1")
    sid = buat_kelas(client, csrf)
    assert client.get(f"/api/v1/subjects/{sid}").json()["nama"] == "Matematika"

    c2 = second_client()
    login(c2, "guru2")
    assert c2.get("/api/v1/subjects").json() == []  # bukan miliknya
    assert c2.get(f"/api/v1/subjects/{sid}").status_code == 403
    assert (
        c2.patch(
            f"/api/v1/subjects/{sid}",
            json={"nama": "Bajak"},
            headers={"x-csrf-token": login(c2, "guru2")},
        ).status_code
        == 403
    )

    res = client.patch(
        f"/api/v1/subjects/{sid}",
        json={"nama": "Matematika Dasar", "deskripsi": "baru"},
        headers={"x-csrf-token": csrf},
    )
    assert res.json()["nama"] == "Matematika Dasar"


def test_meeting_urutan_dan_reorder(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    sid = buat_kelas(client, csrf)
    m1 = buat_pertemuan(client, csrf, sid, "Pertemuan 1")
    m2 = buat_pertemuan(client, csrf, sid, "Pertemuan 2")
    assert (m1["urutan"], m2["urutan"]) == (1, 2)

    res = client.post(
        f"/api/v1/subjects/{sid}/meetings/reorder",
        json={"urutan": [m2["id"], m1["id"]]},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    detail = client.get(f"/api/v1/subjects/{sid}").json()
    assert [m["judul"] for m in detail["meetings"]] == ["Pertemuan 2", "Pertemuan 1"]

    # reorder tidak lengkap -> 400
    res = client.post(
        f"/api/v1/subjects/{sid}/meetings/reorder",
        json={"urutan": [m1["id"]]},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400


def test_enrollment_alur_siswa(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    siswa2_id = make_user("siswa2", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid = buat_kelas(client, csrf)

    res = client.post(
        f"/api/v1/subjects/{sid}/enroll",
        json={"siswa_ids": [siswa_id, siswa_id, 99999]},
        headers={"x-csrf-token": csrf},
    )
    body = res.json()
    assert body["ditambahkan"] == 1
    assert len(body["dilewati"]) == 2  # duplikat + tidak ditemukan

    c_siswa = second_client()
    login(c_siswa, "siswa1")
    daftar = c_siswa.get("/api/v1/subjects").json()
    assert [s["nama"] for s in daftar] == ["Matematika"]
    assert c_siswa.get(f"/api/v1/subjects/{sid}").status_code == 200

    c_siswa2 = second_client()
    login(c_siswa2, "siswa2")
    assert c_siswa2.get(f"/api/v1/subjects/{sid}").status_code == 403

    res = client.delete(
        f"/api/v1/subjects/{sid}/enroll/{siswa_id}", headers={"x-csrf-token": csrf}
    )
    assert res.status_code == 200
    assert c_siswa.get("/api/v1/subjects").json() == []


# ------------------------------------------------------------------ materials
def test_materi_parse_gated_dan_render_cache(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid = buat_kelas(client, csrf)
    meeting = buat_pertemuan(client, csrf, sid)
    client.post(
        f"/api/v1/subjects/{sid}/enroll",
        json={"siswa_ids": [siswa_id]},
        headers={"x-csrf-token": csrf},
    )

    # TCML invalid ditolak + tidak tersimpan
    res = client.post(
        f"/api/v1/meetings/{meeting['id']}/materials",
        json={"judul": "Rusak", "teks_mentah": INVALID_MATERIAL},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400
    detail = client.get(f"/api/v1/subjects/{sid}").json()
    assert detail["meetings"][0]["materials"] == []

    # valid -> tersimpan dengan rendered_html
    res = client.post(
        f"/api/v1/meetings/{meeting['id']}/materials",
        json={"judul": "Pecahan", "teks_mentah": VALID_MATERIAL},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    mat = res.json()
    assert '<h1 class="tc-title">Pecahan Dasar</h1>' in mat["rendered_html"]

    # siswa terdaftar bisa membaca; edit oleh guru me-render ulang
    c_siswa = second_client()
    login(c_siswa, "siswa1")
    assert c_siswa.get(f"/api/v1/materials/{mat['id']}").status_code == 200
    baru = VALID_MATERIAL.replace("Pecahan Dasar", "Pecahan Lanjutan")
    res = client.patch(
        f"/api/v1/materials/{mat['id']}",
        json={"judul": "Pecahan", "teks_mentah": baru},
        headers={"x-csrf-token": csrf},
    )
    assert "Pecahan Lanjutan" in res.json()["rendered_html"]
    # siswa tidak bisa mengubah materi
    assert (
        c_siswa.patch(
            f"/api/v1/materials/{mat['id']}",
            json={"judul": "x", "teks_mentah": baru},
            headers={"x-csrf-token": login(c_siswa, "siswa1")},
        ).status_code
        == 403
    )


def test_lampiran_upload_download(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid = buat_kelas(client, csrf)
    meeting = buat_pertemuan(client, csrf, sid)
    client.post(
        f"/api/v1/subjects/{sid}/enroll",
        json={"siswa_ids": [siswa_id]},
        headers={"x-csrf-token": csrf},
    )
    mat = client.post(
        f"/api/v1/meetings/{meeting['id']}/materials",
        json={"judul": "Dengan Lampiran", "teks_mentah": VALID_MATERIAL},
        headers={"x-csrf-token": csrf},
    ).json()

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    res = client.post(
        f"/api/v1/materials/{mat['id']}/files",
        files={"file": ("gambar.png", png_bytes, "image/png")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    file_id = res.json()["id"]

    # format terlarang ditolak
    res = client.post(
        f"/api/v1/materials/{mat['id']}/files",
        files={"file": ("jahat.exe", b"MZ", "application/octet-stream")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400

    # siswa terdaftar bisa download file yang sama persis
    c_siswa = second_client()
    login(c_siswa, "siswa1")
    dl = c_siswa.get(f"/api/v1/files/{file_id}")
    assert dl.status_code == 200
    assert dl.content == png_bytes

    # siswa lain (tidak terdaftar) tidak bisa
    make_user("luar", "siswa")
    c_luar = second_client()
    login(c_luar, "luar")
    assert c_luar.get(f"/api/v1/files/{file_id}").status_code == 403


# ------------------------------------------------------------------------ bank
def test_bank_materi_dan_pakai(client):
    make_user("guru1", "guru")
    make_user("guru2", "guru")
    csrf = login(client, "guru1")

    res = client.post(
        "/api/v1/bank/categories", json={"nama": "Matematika SD"}, headers={"x-csrf-token": csrf}
    )
    assert res.status_code == 201
    kat_id = res.json()["id"]

    res = client.post(
        "/api/v1/bank/materials",
        json={"judul": "Pecahan", "teks_mentah": VALID_MATERIAL, "kategori_id": kat_id},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    saved_id = res.json()["id"]

    # TCML invalid ditolak di bank juga
    res = client.post(
        "/api/v1/bank/materials",
        json={"judul": "Rusak", "teks_mentah": INVALID_MATERIAL},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400

    # pakai dari bank ke pertemuan
    sid = buat_kelas(client, csrf)
    meeting = buat_pertemuan(client, csrf, sid)
    res = client.post(
        f"/api/v1/meetings/{meeting['id']}/materials/from-bank/{saved_id}",
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    assert '<h1 class="tc-title">Pecahan Dasar</h1>' in res.json()["rendered_html"]

    # guru lain tidak bisa memakai materi bank guru1
    c2 = second_client()
    csrf2 = login(c2, "guru2")
    sid2 = buat_kelas(c2, csrf2, "Kelas Guru2")
    meeting2 = buat_pertemuan(c2, csrf2, sid2)
    res = c2.post(
        f"/api/v1/meetings/{meeting2['id']}/materials/from-bank/{saved_id}",
        headers={"x-csrf-token": csrf2},
    )
    assert res.status_code == 404

    # hapus kategori -> kategori_id materi jadi NULL, materi tetap ada
    client.delete(f"/api/v1/bank/categories/{kat_id}", headers={"x-csrf-token": csrf})
    rows = client.get("/api/v1/bank/materials").json()
    assert len(rows) == 1 and rows[0]["kategori_id"] is None


def test_arsip_subject(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid = buat_kelas(client, csrf)
    client.post(
        f"/api/v1/subjects/{sid}/enroll",
        json={"siswa_ids": [siswa_id]},
        headers={"x-csrf-token": csrf},
    )
    res = client.patch(
        f"/api/v1/subjects/{sid}",
        json={"is_archived": True},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    assert res.json()["is_archived"] is True
    # hilang dari daftar default guru & siswa, muncul saat diminta
    assert client.get("/api/v1/subjects").json() == []
    rows = client.get("/api/v1/subjects?termasuk_arsip=true").json()
    assert len(rows) == 1
    c_siswa = second_client()
    login(c_siswa, "siswa1")
    assert c_siswa.get("/api/v1/subjects").json() == []
    # batalkan arsip -> kembali terlihat
    client.patch(
        f"/api/v1/subjects/{sid}",
        json={"is_archived": False},
        headers={"x-csrf-token": csrf},
    )
    assert len(client.get("/api/v1/subjects").json()) == 1


def test_bank_kuis_snapshot(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    res = client.post(
        "/api/v1/bank/quizzes",
        json={"judul": "Kuis Tambah", "tipe": "pilihan_ganda", "teks_mentah": VALID_QUIZ_PG},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    assert res.json()["jumlah_soal"] == 1
    rows = client.get("/api/v1/bank/quizzes").json()
    assert rows[0]["judul"] == "Kuis Tambah"
