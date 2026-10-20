"""Test paket UX (audit U4+U5): dashboard antrean + siswa langsung di kelas."""

import io

from conftest import login, make_user
from fastapi.testclient import TestClient

from app.main import app

PROYEK = "[PROJECT]\n[TITLE]Poster[/TITLE]\n[DESCRIPTION]Buat poster.[/DESCRIPTION]\n[/PROJECT]"
ESAI = """[QUIZ]
[TYPE]essay[/TYPE]
[QUESTION 1]
[QUESTION]Jelaskan fotosintesis.[/QUESTION]
[ANSWER]Referensi.[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""


def test_buat_siswa_langsung_di_kelas(client):
    make_user("guru1", "guru")
    make_user("guru2", "guru")
    csrf = login(client, "guru1")
    sid = client.post("/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}).json()["id"]

    res = client.post(
        f"/api/v1/subjects/{sid}/students/create",
        json={"username": "rani", "nama_lengkap": "Rani P", "password": "password123"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    assert res.json()["terdaftar_di_kelas"] == sid

    members = client.get(f"/api/v1/subjects/{sid}/students").json()
    assert any(m["username"] == "rani" for m in members)

    # siswa hasil buat langsung bisa login & melihat kelasnya
    c = TestClient(app)
    login(c, "rani", "password123")
    assert c.get(f"/api/v1/subjects/{sid}").status_code == 200

    # guru lain (bukan pengelola) tidak boleh
    c2 = TestClient(app)
    csrf2 = login(c2, "guru2")
    res = c2.post(
        f"/api/v1/subjects/{sid}/students/create",
        json={"username": "ilegal", "password": "password123"},
        headers={"x-csrf-token": csrf2},
    )
    assert res.status_code == 403


def test_impor_csv_langsung_ke_kelas(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    sid = client.post("/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}).json()["id"]

    csv_text = "username,nama_lengkap,password\nbima,Bima A,password123\nsalsa,Salsa Z,password123\n"
    res = client.post(
        "/api/v1/users/students/import",
        files={"file": ("siswa.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        data={"subject_id": str(sid)},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200, res.text
    assert res.json()["berhasil"] == 2
    members = client.get(f"/api/v1/subjects/{sid}/students").json()
    assert {m["username"] for m in members} == {"bima", "salsa"}


def test_dashboard_antrean_guru_dan_siswa(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid = client.post("/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf}).json()["id"]
    client.post(f"/api/v1/subjects/{sid}/enroll", json={"siswa_ids": [siswa_id]}, headers={"x-csrf-token": csrf})
    quiz = client.post(
        f"/api/v1/meetings/{mid}/quizzes",
        json={"judul": "Esai 1", "tipe": "teks", "teks_mentah": ESAI},
        headers={"x-csrf-token": csrf},
    ).json()
    proyek = client.post(
        f"/api/v1/meetings/{mid}/materials",
        json={"judul": "Proyek 1", "teks_mentah": PROYEK},
        headers={"x-csrf-token": csrf},
    ).json()

    dash = client.get("/api/v1/dashboard").json()
    assert dash["mode"] == "guru"
    assert dash["perlu_dinilai"]["esai"] == []
    assert dash["kelas_saya"][0]["nama"] == "IPA"

    # siswa mengerjakan esai + mengumpulkan tugas
    c = TestClient(app)
    csrf_s = login(c, "siswa1")
    attempt_id = c.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s}).json()["attempt"]["id"]
    qid = quiz["questions"][0]["id"]
    c.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        json={"answers": [{"question_id": qid, "jawaban_teks": "Jawaban."}]},
        headers={"x-csrf-token": csrf_s},
    )
    c.post(
        f"/api/v1/materials/{proyek['id']}/submissions",
        files={"file": ("poster.txt", b"isi poster", "text/plain")},
        headers={"x-csrf-token": csrf_s},
    )

    dash = client.get("/api/v1/dashboard").json()
    assert dash["perlu_dinilai"]["esai"][0]["jumlah"] == 1
    assert dash["perlu_dinilai"]["esai"][0]["judul"] == "Esai 1"
    assert dash["perlu_dinilai"]["tugas"][0]["jumlah"] == 1

    # setelah esai dinilai, antrean esai kosong
    client.post(
        f"/api/v1/attempts/{attempt_id}/grade",
        json={"grades": [{"question_id": qid, "poin": 1}]},
        headers={"x-csrf-token": csrf},
    )
    dash = client.get("/api/v1/dashboard").json()
    assert dash["perlu_dinilai"]["esai"] == []

    # dashboard siswa: kelas + progress
    dash_s = c.get("/api/v1/dashboard").json()
    assert dash_s["mode"] == "siswa"
    assert dash_s["kelas"][0]["nama"] == "IPA"
    assert dash_s["kelas"][0]["kuis_dikerjakan"] == 1


# ------------------------------------------------------- navigasi materi (audit UX 2)
def test_navigasi_materi_sebelum_sesudah(client):
    """GET materi menyertakan navigasi sebelumnya/berikutnya mengikuti urutan
    pertemuan lalu urutan materi — lintas pertemuan."""
    from tests.test_fase2 import VALID_MATERIAL, buat_kelas, buat_pertemuan

    make_user("gnav", "guru")
    csrf = login(client, "gnav")
    sid = buat_kelas(client, csrf, "Kelas Navigasi")
    p1 = buat_pertemuan(client, csrf, sid, "Pertemuan 1")
    p2 = buat_pertemuan(client, csrf, sid, "Pertemuan 2")

    def materi(meeting_id, judul):
        r = client.post(
            f"/api/v1/meetings/{meeting_id}/materials",
            json={"judul": judul, "teks_mentah": VALID_MATERIAL},
            headers={"x-csrf-token": csrf},
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    m1 = materi(p1["id"], "Materi A")
    m2 = materi(p1["id"], "Materi B")
    m3 = materi(p2["id"], "Materi C")

    nav1 = client.get(f"/api/v1/materials/{m1}").json()["navigasi"]
    assert nav1["sebelumnya"] is None
    assert nav1["berikutnya"]["id"] == m2

    nav2 = client.get(f"/api/v1/materials/{m2}").json()["navigasi"]
    assert nav2["sebelumnya"]["id"] == m1
    assert nav2["berikutnya"]["id"] == m3  # menyeberang ke pertemuan berikutnya

    nav3 = client.get(f"/api/v1/materials/{m3}").json()["navigasi"]
    assert nav3["sebelumnya"]["id"] == m2
    assert nav3["berikutnya"] is None
