"""Test paket perbaikan 2026-10-20: penanda bank, ekstrak dari kuis bank,
dan Template Kelas."""

from conftest import login, make_user

MATERI = "[MATERIAL]\n[TITLE]M1[/TITLE]\nIsi materi.\n[/MATERIAL]"
KUIS_PG = """[QUIZ]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]Ibu kota Indonesia?[/QUESTION]
[OPTIONS]
A. Bandung
B. Jakarta
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/QUESTION 1]
[QUESTION 2]
[QUESTION]2+2?[/QUESTION]
[OPTIONS]
A. 3
B. 4
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/QUESTION 2]
[/QUIZ]"""


def _kelas_dengan_isi(client, csrf):
    sid = client.post("/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf}).json()["id"]
    mat = client.post(
        f"/api/v1/meetings/{mid}/materials",
        json={"judul": "M1", "teks_mentah": MATERI},
        headers={"x-csrf-token": csrf},
    ).json()
    quiz = client.post(
        f"/api/v1/meetings/{mid}/quizzes",
        json={"judul": "K1", "tipe": "pilihan_ganda", "teks_mentah": KUIS_PG, "durasi_menit": 30},
        headers={"x-csrf-token": csrf},
    ).json()
    return sid, mid, mat, quiz


def test_simpan_bank_penanda_dan_flag(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    sid, mid, mat, quiz = _kelas_dengan_isi(client, csrf)

    detail = client.get(f"/api/v1/subjects/{sid}").json()
    m0 = detail["meetings"][0]
    assert m0["materials"][0]["di_bank"] is False
    assert m0["quizzes"][0]["di_bank"] is False

    r = client.post(f"/api/v1/materials/{mat['id']}/save-to-bank", headers={"x-csrf-token": csrf})
    assert r.status_code == 201, r.text
    # kedua kali -> ditolak (sekali simpan, tidak bisa lagi)
    r = client.post(f"/api/v1/materials/{mat['id']}/save-to-bank", headers={"x-csrf-token": csrf})
    assert r.status_code == 400

    r = client.post(f"/api/v1/quizzes/{quiz['id']}/save-to-bank", json={}, headers={"x-csrf-token": csrf})
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/quizzes/{quiz['id']}/save-to-bank", json={}, headers={"x-csrf-token": csrf})
    assert r.status_code == 400

    detail = client.get(f"/api/v1/subjects/{sid}").json()
    m0 = detail["meetings"][0]
    assert m0["materials"][0]["di_bank"] is True
    assert m0["quizzes"][0]["di_bank"] is True

    # walau materi diedit, tetap tidak bisa disimpan lagi (penanda, bukan teks)
    client.patch(
        f"/api/v1/materials/{mat['id']}",
        json={"judul": "M1 revisi", "teks_mentah": MATERI.replace("Isi materi", "Isi BARU")},
        headers={"x-csrf-token": csrf},
    )
    r = client.post(f"/api/v1/materials/{mat['id']}/save-to-bank", headers={"x-csrf-token": csrf})
    assert r.status_code == 400


def test_ekstrak_dari_kuis_bank(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    sid, mid, mat, quiz = _kelas_dengan_isi(client, csrf)
    client.post(f"/api/v1/quizzes/{quiz['id']}/save-to-bank", json={}, headers={"x-csrf-token": csrf})
    saved = client.get("/api/v1/bank/quizzes").json()
    assert len(saved) == 1

    r = client.post(f"/api/v1/bank/quizzes/{saved[0]['id']}/extract-questions", headers={"x-csrf-token": csrf})
    assert r.status_code == 201, r.text
    assert r.json() == {"ok": True, "dimasukkan": 2, "dilewati": 0}

    # ekstrak ulang -> semua dilewati (sudah ada)
    r = client.post(f"/api/v1/bank/quizzes/{saved[0]['id']}/extract-questions", headers={"x-csrf-token": csrf})
    assert r.json() == {"ok": True, "dimasukkan": 0, "dilewati": 2}
    assert len(client.get("/api/v1/bank/questions").json()) == 2


def test_template_kelas_roundtrip(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid, mid, mat, quiz = _kelas_dengan_isi(client, csrf)
    # lampiran pada materi asal
    client.post(
        f"/api/v1/materials/{mat['id']}/files",
        files={"file": ("catatan.pdf", b"%PDF-1.4 isi catatan", "application/pdf")},
        headers={"x-csrf-token": csrf},
    )
    client.post(f"/api/v1/subjects/{sid}/enroll", json={"siswa_ids": [siswa_id]}, headers={"x-csrf-token": csrf})

    r = client.post(f"/api/v1/subjects/{sid}/save-template", json={"nama": "Paket IPA Dasar"}, headers={"x-csrf-token": csrf})
    assert r.status_code == 201, r.text
    tpl = r.json()
    assert tpl["jumlah_pertemuan"] == 1 and tpl["jumlah_materi"] == 1 and tpl["jumlah_kuis"] == 1

    r = client.post(
        f"/api/v1/class-templates/{tpl['id']}/instantiate",
        json={"nama": "IPA Kelas Baru"},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]
    detail = client.get(f"/api/v1/subjects/{new_id}").json()
    assert detail["nama"] == "IPA Kelas Baru"
    m0 = detail["meetings"][0]
    assert m0["judul"] == "P1" and m0["tanggal"] is None  # tanggal tidak disalin
    assert m0["materials"][0]["judul"] == "M1"
    assert m0["materials"][0]["jumlah_file"] == 1  # lampiran ikut tersalin
    assert m0["quizzes"][0]["judul"] == "K1"
    # siswa TIDAK ikut; kelas baru kosong
    assert client.get(f"/api/v1/subjects/{new_id}/students").json() == []
    # soal kuis salinan terbangun (bisa dikerjakan) & durasi ikut, jendela kosong
    q = client.get(f"/api/v1/quizzes/{m0['quizzes'][0]['id']}").json()
    assert q["durasi_menit"] == 30
    assert q["dibuka_pada"] is None and q["ditutup_pada"] is None
    assert len(q["questions"]) == 2

    # lampiran salinan bisa diunduh
    files = client.get(f"/api/v1/materials/{m0['materials'][0]['id']}").json()["files"]
    dl = client.get(f"/api/v1/files/{files[0]['id']}")
    assert dl.status_code == 200 and dl.content == b"%PDF-1.4 isi catatan"

    # template guru lain tidak bisa dipakai
    from fastapi.testclient import TestClient

    from app.main import app

    make_user("guru2", "guru")
    c2 = TestClient(app)
    csrf2 = login(c2, "guru2")
    r = c2.post(
        f"/api/v1/class-templates/{tpl['id']}/instantiate",
        json={"nama": "Bajakan"},
        headers={"x-csrf-token": csrf2},
    )
    assert r.status_code == 404

    # hapus template
    r = client.delete(f"/api/v1/class-templates/{tpl['id']}", headers={"x-csrf-token": csrf})
    assert r.status_code == 200
    assert client.get("/api/v1/class-templates").json() == []
