"""Test Fase 4: salin bank antar guru, bank soal, susun kuis acak."""

from conftest import login, make_user
from fastapi.testclient import TestClient

from app.tcml.quiz import parse_quiz_v2

MATERI_TCML = "[MATERIAL]\n[TITLE]Materi A[/TITLE]\nIsi materi biasa.\n[/MATERIAL]"
PG_TCML = """[QUIZ]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]2 + 2 = ?[/QUESTION]
[OPTIONS]
A. 3
B. 4
[/OPTIONS]
[ANSWER]B[/ANSWER]
[WEIGHT]2[/WEIGHT]
[/QUESTION 1]
[QUESTION 2]
[QUESTION]Ibu kota Jepang?[/QUESTION]
[OPTIONS]
A. Seoul
B. Tokyo
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/QUESTION 2]
[/QUIZ]"""


def buat_soal_pg(client, csrf, pertanyaan, benar_label="B", kategori_id=None, bobot=1):
    body = {
        "tipe": "pilihan_ganda",
        "pertanyaan": pertanyaan,
        "bobot": bobot,
        "options": [
            {"label": "A", "teks": "Pilihan salah", "is_correct": benar_label == "A"},
            {"label": "B", "teks": "Pilihan benar", "is_correct": benar_label == "B"},
        ],
    }
    if kategori_id:
        body["kategori_id"] = kategori_id
    res = client.post("/api/v1/bank/questions", json=body, headers={"x-csrf-token": csrf})
    assert res.status_code == 201, res.text
    return res.json()


# ------------------------------------------------------------ salin antar guru
def test_salin_bank_antar_guru(client):
    from app.main import app

    make_user("guru1", "guru")
    make_user("guru2", "guru")
    csrf1 = login(client, "guru1")
    res = client.post(
        "/api/v1/bank/materials",
        json={"judul": "Milik Guru1", "teks_mentah": MATERI_TCML},
        headers={"x-csrf-token": csrf1},
    )
    mat_id = res.json()["id"]
    res = client.post(
        "/api/v1/bank/quizzes",
        json={"judul": "Kuis Guru1", "tipe": "pilihan_ganda", "teks_mentah": PG_TCML},
        headers={"x-csrf-token": csrf1},
    )
    quiz_bank_id = res.json()["id"]

    c2 = TestClient(app)
    csrf2 = login(c2, "guru2")
    # guru2 belum punya apa-apa, tapi bisa menjelajah bank guru1
    assert c2.get("/api/v1/bank/materials").json() == []
    explore = c2.get("/api/v1/bank/explore/materials").json()
    assert len(explore) == 1 and explore[0]["pemilik"]["username"] == "guru1"
    explore_q = c2.get("/api/v1/bank/explore/quizzes").json()
    assert len(explore_q) == 1 and explore_q[0]["jumlah_soal"] == 2

    # salin -> jadi milik guru2, guru1 tidak terpengaruh
    res = c2.post(f"/api/v1/bank/materials/{mat_id}/copy", headers={"x-csrf-token": csrf2})
    assert res.status_code == 201
    assert res.json()["judul"] == "Milik Guru1"
    res = c2.post(f"/api/v1/bank/quizzes/{quiz_bank_id}/copy", headers={"x-csrf-token": csrf2})
    assert res.status_code == 201
    assert len(c2.get("/api/v1/bank/materials").json()) == 1
    assert len(c2.get("/api/v1/bank/quizzes").json()) == 1
    assert len(client.get("/api/v1/bank/materials").json()) == 1  # guru1 tetap 1 (aslinya)

    # siswa dilarang menjelajah
    make_user("siswa1", "siswa")
    c3 = TestClient(app)
    login(c3, "siswa1")
    assert c3.get("/api/v1/bank/explore/materials").status_code == 403


# ------------------------------------------------------------------ bank soal
def test_bank_soal_crud_dan_validasi(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    q = buat_soal_pg(client, csrf, "Apa warna langit?", bobot=2)
    assert q["bobot"] == 2
    assert q["options"][1]["is_correct"] is True

    # PG tanpa jawaban benar -> 400
    res = client.post(
        "/api/v1/bank/questions",
        json={
            "tipe": "pilihan_ganda",
            "pertanyaan": "X?",
            "options": [
                {"label": "A", "teks": "a", "is_correct": False},
                {"label": "B", "teks": "b", "is_correct": False},
            ],
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400

    # esai
    res = client.post(
        "/api/v1/bank/questions",
        json={"tipe": "teks", "pertanyaan": "Jelaskan gravitasi.", "jawaban_referensi": "Gaya tarik massa."},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    rows = client.get("/api/v1/bank/questions").json()
    assert len(rows) == 2
    rows_pg = client.get("/api/v1/bank/questions?tipe=pilihan_ganda").json()
    assert len(rows_pg) == 1

    # hapus
    res = client.delete(f"/api/v1/bank/questions/{q['id']}", headers={"x-csrf-token": csrf})
    assert res.status_code == 200
    assert len(client.get("/api/v1/bank/questions").json()) == 1


def _kelas_dengan_kuis(client, csrf):
    sid = client.post("/api/v1/subjects", json={"nama": "Umum"}, headers={"x-csrf-token": csrf}).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf}).json()["id"]
    quiz = client.post(
        f"/api/v1/meetings/{mid}/quizzes",
        json={"judul": "Kuis Sumber", "tipe": "pilihan_ganda", "teks_mentah": PG_TCML},
        headers={"x-csrf-token": csrf},
    ).json()
    return sid, mid, quiz


def test_ekstrak_soal_dari_kuis(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, _, quiz = _kelas_dengan_kuis(client, csrf)
    res = client.post(
        f"/api/v1/quizzes/{quiz['id']}/extract-questions",
        json={},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    assert res.json()["jumlah_diekstrak"] == 2
    rows = client.get("/api/v1/bank/questions").json()
    assert len(rows) == 2
    q1 = next(r for r in rows if r["pertanyaan"].startswith("2 + 2"))
    assert q1["bobot"] == 2.0
    assert [o["label"] for o in q1["options"] if o["is_correct"]] == ["B"]


def test_susun_kuis_acak_dari_bank_soal(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    sid = client.post("/api/v1/subjects", json={"nama": "MTK"}, headers={"x-csrf-token": csrf}).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "Ulangan"}, headers={"x-csrf-token": csrf}).json()["id"]
    for i in range(5):
        buat_soal_pg(client, csrf, f"Soal nomor {i + 1}?")

    # minta lebih dari stok -> 400 jujur
    res = client.post(
        f"/api/v1/meetings/{mid}/quizzes/from-bank-questions",
        json={"judul": "Kebanyakan", "jumlah": 9},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400
    assert "tersedia 5" in res.json()["detail"]

    # susun 3 soal
    res = client.post(
        f"/api/v1/meetings/{mid}/quizzes/from-bank-questions",
        json={"judul": "Ulangan Acak", "jumlah": 3, "durasi_menit": 20},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    quiz = res.json()
    assert len(quiz["questions"]) == 3
    assert quiz["durasi_menit"] == 20
    # teks TCML hasil generate harus roundtrip valid & isinya sama
    reparsed = parse_quiz_v2(quiz["teks_mentah"], expected_type="pilihan_ganda")
    assert reparsed["success"], reparsed["errors"]
    assert {q["pertanyaan"] for q in reparsed["content"]["questions"]} == {
        q["pertanyaan"] for q in quiz["questions"]
    }
    kunci = {
        o["label"]
        for q in reparsed["content"]["questions"]
        for o in q["options"]
        if o["is_correct"]
    }
    assert kunci == {"B"}


def test_susun_dari_bank_guru_lain_ditolak(client):
    from app.main import app

    make_user("guru1", "guru")
    make_user("guru2", "guru")
    csrf1 = login(client, "guru1")
    for i in range(3):
        buat_soal_pg(client, csrf1, f"Soal guru1 {i}?")

    c2 = TestClient(app)
    csrf2 = login(c2, "guru2")
    sid = c2.post("/api/v1/subjects", json={"nama": "X"}, headers={"x-csrf-token": csrf2}).json()["id"]
    mid = c2.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf2}).json()["id"]
    res = c2.post(
        f"/api/v1/meetings/{mid}/quizzes/from-bank-questions",
        json={"judul": "Nyolong", "jumlah": 2},
        headers={"x-csrf-token": csrf2},
    )
    assert res.status_code == 400  # bank guru2 kosong
    assert "tersedia 0" in res.json()["detail"]
