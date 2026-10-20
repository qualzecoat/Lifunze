"""Test Fase 6: progress, pengumuman, notifikasi, tugas file, mode hemat."""

import io

from conftest import login, make_user
from fastapi.testclient import TestClient

from app.main import app

MATERI = "[MATERIAL]\n[TITLE]Bab 1[/TITLE]\nIsi bab satu.\n[/MATERIAL]"
PROYEK = """[PROJECT]
[TITLE]Poster Hemat Air[/TITLE]
[DESCRIPTION]Buat poster kampanye hemat air.[/DESCRIPTION]
[OUTPUT]Foto poster.[/OUTPUT]
[RUBRIC]Kreativitas 50, isi 50.[/RUBRIC]
[/PROJECT]"""
ESAI = """[QUIZ]
[TYPE]essay[/TYPE]
[QUESTION 1]
[QUESTION]Jelaskan fotosintesis.[/QUESTION]
[ANSWER]Referensi.[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""


def setup(client, csrf, siswa_ids=()):
    sid = client.post("/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf}).json()["id"]
    if siswa_ids:
        client.post(
            f"/api/v1/subjects/{sid}/enroll",
            json={"siswa_ids": list(siswa_ids)},
            headers={"x-csrf-token": csrf},
        )
    return sid, mid


def buat_materi(client, csrf, mid, teks=MATERI, judul="Materi 1"):
    res = client.post(
        f"/api/v1/meetings/{mid}/materials",
        json={"judul": judul, "teks_mentah": teks},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    return res.json()


def notif(client, tipe=None):
    data = client.get("/api/v1/notifications").json()
    items = data["items"]
    if tipe:
        items = [i for i in items if i["tipe"] == tipe]
    return items, data["belum_dibaca"]


# ------------------------------------------------------------------ progress
def test_progress_dan_tandai_dibaca(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid, mid = setup(client, csrf, [siswa_id])
    mat = buat_materi(client, csrf, mid)

    c = TestClient(app)
    csrf_s = login(c, "siswa1")
    prog = c.get(f"/api/v1/subjects/{sid}/progress").json()
    assert prog["ringkasan"]["persen_materi"] == 0.0

    res = c.post(f"/api/v1/materials/{mat['id']}/read", headers={"x-csrf-token": csrf_s})
    assert res.status_code == 200
    # idempoten
    res = c.post(f"/api/v1/materials/{mat['id']}/read", headers={"x-csrf-token": csrf_s})
    assert res.status_code == 200

    prog = c.get(f"/api/v1/subjects/{sid}/progress").json()
    assert prog["ringkasan"]["materi_dibaca"] == 1
    assert prog["ringkasan"]["persen_materi"] == 100.0

    guru_view = client.get(f"/api/v1/subjects/{sid}/progress").json()
    assert guru_view["mode"] == "guru"
    assert guru_view["per_siswa"][0]["persen_total"] == 100.0


def test_pengumuman_dan_notifikasi(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid, _ = setup(client, csrf, [siswa_id])

    res = client.post(
        f"/api/v1/subjects/{sid}/announcements",
        json={"judul": "Ulangan besok", "isi": "Bab 1-3."},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201

    c = TestClient(app)
    csrf_s = login(c, "siswa1")
    rows = c.get(f"/api/v1/subjects/{sid}/announcements").json()
    assert rows[0]["judul"] == "Ulangan besok"
    items, unread = notif(c, "pengumuman")
    assert len(items) == 1 and unread == 1

    c.post("/api/v1/notifications/read-all", headers={"x-csrf-token": csrf_s})
    _, unread = notif(c)
    assert unread == 0

    # siswa tidak boleh membuat pengumuman
    res = c.post(
        f"/api/v1/subjects/{sid}/announcements",
        json={"judul": "X", "isi": "Y"},
        headers={"x-csrf-token": csrf_s},
    )
    assert res.status_code == 403


def test_notifikasi_kuis_baru_dan_alur_esai(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid, mid = setup(client, csrf, [siswa_id])

    quiz = client.post(
        f"/api/v1/meetings/{mid}/quizzes",
        json={"judul": "Esai 1", "tipe": "teks", "teks_mentah": ESAI},
        headers={"x-csrf-token": csrf},
    ).json()

    c = TestClient(app)
    csrf_s = login(c, "siswa1")
    items, _ = notif(c, "kuis_baru")
    assert len(items) == 1 and items[0]["payload"]["quiz_id"] == quiz["id"]

    attempt_id = c.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s}).json()["attempt"]["id"]
    qid = quiz["questions"][0]["id"]
    c.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        json={"answers": [{"question_id": qid, "jawaban_teks": "Jawaban siswa."}]},
        headers={"x-csrf-token": csrf_s},
    )
    items, _ = notif(client, "attempt_masuk")
    assert len(items) == 1

    client.post(
        f"/api/v1/attempts/{attempt_id}/grade",
        json={"grades": [{"question_id": qid, "poin": 1}]},
        headers={"x-csrf-token": csrf},
    )
    items, _ = notif(c, "nilai_keluar")
    assert len(items) == 1 and items[0]["payload"]["skor"] == 100.0


# --------------------------------------------------------------- tugas file
def test_submission_proyek_dan_rubrik(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    make_user("siswa2", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid, mid = setup(client, csrf, [siswa_id])
    proyek = buat_materi(client, csrf, mid, teks=PROYEK, judul="Proyek 1")
    biasa = buat_materi(client, csrf, mid, teks=MATERI, judul="Materi Biasa")

    c = TestClient(app)
    csrf_s = login(c, "siswa1")
    # materi biasa -> 400
    res = c.post(
        f"/api/v1/materials/{biasa['id']}/submissions",
        files={"file": ("tugas.txt", b"isi", "text/plain")},
        headers={"x-csrf-token": csrf_s},
    )
    assert res.status_code == 400

    # proyek -> ok
    res = c.post(
        f"/api/v1/materials/{proyek['id']}/submissions",
        files={"file": ("poster.txt", b"poster v1", "text/plain")},
        data={"catatan": "versi 1"},
        headers={"x-csrf-token": csrf_s},
    )
    assert res.status_code == 201, res.text
    sub = res.json()
    assert sub["nama_file"] == "poster.txt"

    # kumpul ulang menggantikan
    res = c.post(
        f"/api/v1/materials/{proyek['id']}/submissions",
        files={"file": ("poster2.txt", b"poster v2", "text/plain")},
        headers={"x-csrf-token": csrf_s},
    )
    assert res.status_code == 201
    rows = client.get(f"/api/v1/materials/{proyek['id']}/submissions").json()
    assert len(rows["submissions"]) == 1
    assert rows["submissions"][0]["nama_file"] == "poster2.txt"

    # nilai dengan rubrik
    res = client.post(
        f"/api/v1/submissions/{sub['id']}/grade",
        json={
            "skor": 88,
            "feedback_rubrik": {
                "items": [
                    {"kriteria": "Kreativitas", "poin": 45, "maks": 50, "komentar": "Bagus"},
                    {"kriteria": "Isi", "poin": 43, "maks": 50, "komentar": "Lengkap"},
                ]
            },
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    mine = c.get(f"/api/v1/materials/{proyek['id']}/submissions").json()
    assert mine["submissions"][0]["skor"] == 88
    assert mine["submissions"][0]["feedback_rubrik"]["items"][0]["kriteria"] == "Kreativitas"

    # unduh oleh pemilik ok; notifikasi nilai keluar diterima siswa
    res = c.get(f"/api/v1/submissions/{sub['id']}/download")
    assert res.status_code == 200 and res.content == b"poster v2"
    items, _ = notif(c, "nilai_keluar")
    assert any(i["payload"].get("submission_id") == sub["id"] for i in items)


# ---------------------------------------------------------------- mode hemat
def test_mode_hemat_gambar(client):
    from PIL import Image

    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    sid, mid = setup(client, csrf, [siswa_id])
    mat = buat_materi(client, csrf, mid)

    # PNG noise besar: PNG tidak bisa mengompres noise, JPEG jauh lebih kecil
    import random

    random.seed(42)
    img = Image.new("RGB", (1600, 900))
    px = img.load()
    for x in range(0, 1600, 2):
        for y in range(0, 900, 2):
            px[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    png_bytes = buf.getvalue()

    res = client.post(
        f"/api/v1/materials/{mat['id']}/files",
        files={"file": ("foto.png", png_bytes, "image/png")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    file_id = res.json()["id"]

    asli = client.get(f"/api/v1/files/{file_id}")
    assert asli.headers["content-type"] == "image/png"
    assert asli.content == png_bytes

    hemat = client.get(f"/api/v1/files/{file_id}?hemat=true")
    assert hemat.headers["content-type"] == "image/jpeg"
    assert len(hemat.content) < len(png_bytes)

    hemat2 = client.get(f"/api/v1/files/{file_id}?hemat=true")
    assert hemat2.content == hemat.content  # cache konsisten
