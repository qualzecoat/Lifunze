"""Test Fase 3: kuis v2 — CRUD, attempts, penilaian PG/esai, export, bank."""

from datetime import datetime, timedelta, timezone

from conftest import login, make_user
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import QuizAttempt

PG_TCML = """[QUIZ]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]Pilih bilangan prima.[/QUESTION]
[OPTIONS]
A. 4
B. 5
C. 7
D. 9
[/OPTIONS]
[ANSWER]B, C[/ANSWER]
[WEIGHT]2[/WEIGHT]
[/QUESTION 1]
[QUESTION 2]
[QUESTION]1 + 1 = ?[/QUESTION]
[OPTIONS]
A. 1
B. 2
C. 3
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/QUESTION 2]
[/QUIZ]"""

ESAI_TCML = """[QUIZ]
[TYPE]essay[/TYPE]
[QUESTION 1]
[QUESTION]Jelaskan fotosintesis.[/QUESTION]
[ANSWER]Tumbuhan membuat makanan dari cahaya.[/ANSWER]
[WEIGHT]3[/WEIGHT]
[/QUESTION 1]
[QUESTION 2]
[QUESTION]Sebutkan hasil fotosintesis.[/QUESTION]
[/QUESTION 2]
[/QUIZ]"""


def second_client():
    return TestClient(app)


def setup_kelas(client, csrf, enroll_ids=()):
    sid = client.post(
        "/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}
    ).json()["id"]
    mid = client.post(
        f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf}
    ).json()["id"]
    if enroll_ids:
        client.post(
            f"/api/v1/subjects/{sid}/enroll",
            json={"siswa_ids": list(enroll_ids)},
            headers={"x-csrf-token": csrf},
        )
    return sid, mid


def buat_kuis(client, csrf, mid, tcml=PG_TCML, tipe="pilihan_ganda", **settings):
    body = {"judul": "Kuis Uji", "tipe": tipe, "teks_mentah": tcml}
    body.update(settings)
    res = client.post(
        f"/api/v1/meetings/{mid}/quizzes", json=body, headers={"x-csrf-token": csrf}
    )
    assert res.status_code == 201, res.text
    return res.json()


def opsi_ids(question, benar=None):
    """Ambil id opsi; benar=True -> hanya yang benar, False -> hanya yang salah."""
    out = []
    for o in question["options"]:
        if benar is None or o["is_correct"] == benar:
            out.append(o["id"])
    return out


# --------------------------------------------------------------------- CRUD
def test_kuis_crud_dan_parse_gated(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf)
    quiz = buat_kuis(client, csrf, mid)
    q1 = quiz["questions"][0]
    assert q1["bobot"] == 2.0
    assert [o["label"] for o in q1["options"] if o["is_correct"]] == ["B", "C"]
    assert quiz["questions"][1]["bobot"] == 1.0

    # invalid -> 400
    res = client.post(
        f"/api/v1/meetings/{mid}/quizzes",
        json={"judul": "X", "tipe": "pilihan_ganda", "teks_mentah": "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n[/QUIZ]"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400

    # patch teks setelah ada attempt -> ditolak (diuji di test attempt terpisah);
    # di sini patch pengaturan saja
    res = client.patch(
        f"/api/v1/quizzes/{quiz['id']}",
        json={"durasi_menit": 30},
        headers={"x-csrf-token": csrf},
    )
    assert res.json()["durasi_menit"] == 30


def test_attempt_pg_penilaian_berbobot(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf, enroll_ids=[siswa_id])
    quiz = buat_kuis(client, csrf, mid)

    c = second_client()
    csrf_s = login(c, "siswa1")
    # tampilan siswa: tanpa kunci
    info = c.get(f"/api/v1/quizzes/{quiz['id']}").json()
    assert info["bisa_mulai"] is True
    assert "questions" not in info

    res = c.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s})
    assert res.status_code == 201
    attempt = res.json()
    attempt_id = attempt["attempt"]["id"]
    assert all("is_correct" not in o for q in attempt["questions"] for o in q["options"])
    assert attempt["questions"][0]["multi"] is True

    # jawab: Q1 benar persis (bobot 2), Q2 salah (bobot 1) -> skor 2/3 = 66.67
    full = client.get(f"/api/v1/quizzes/{quiz['id']}").json()  # guru: ada kunci
    answers = []
    for q in full["questions"]:
        if q["pertanyaan"].startswith("Pilih"):
            answers.append({"question_id": q["id"], "option_ids": opsi_ids(q, benar=True)})
        else:
            answers.append({"question_id": q["id"], "option_ids": opsi_ids(q, benar=False)[:1]})
    res = c.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        json={"answers": answers},
        headers={"x-csrf-token": csrf_s},
    )
    body = res.json()
    assert body["attempt"]["status"] == "submitted"
    assert body["attempt"]["skor"] == 66.67
    # kunci tampil ke siswa setelah submit (tampilkan_kunci default True)
    assert body["questions"][0]["kunci_option_ids"]

    # tidak bisa mengerjakan ulang
    res = c.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s})
    assert res.status_code == 400


def test_multi_jawaban_harus_persis(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf, enroll_ids=[siswa_id])
    quiz = buat_kuis(client, csrf, mid)
    full = client.get(f"/api/v1/quizzes/{quiz['id']}").json()

    c = second_client()
    csrf_s = login(c, "siswa1")
    attempt_id = c.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s}
    ).json()["attempt"]["id"]
    answers = []
    for q in full["questions"]:
        if q["pertanyaan"].startswith("Pilih"):
            answers.append({"question_id": q["id"], "option_ids": opsi_ids(q, benar=True)[:1]})  # subset -> salah
        else:
            answers.append({"question_id": q["id"], "option_ids": opsi_ids(q, benar=True)})
    res = c.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        json={"answers": answers},
        headers={"x-csrf-token": csrf_s},
    )
    # hanya Q2 benar (bobot 1 dari total 3) -> 33.33
    assert res.json()["attempt"]["skor"] == 33.33


def test_jendela_waktu(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf, enroll_ids=[siswa_id])
    masa_depan = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    quiz = buat_kuis(client, csrf, mid, dibuka_pada=masa_depan)

    c = second_client()
    csrf_s = login(c, "siswa1")
    info = c.get(f"/api/v1/quizzes/{quiz['id']}").json()
    assert info["bisa_mulai"] is False
    res = c.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s})
    assert res.status_code == 400


def test_durasi_auto_expire_dengan_draf(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf, enroll_ids=[siswa_id])
    quiz = buat_kuis(client, csrf, mid, durasi_menit=10)
    full = client.get(f"/api/v1/quizzes/{quiz['id']}").json()

    c = second_client()
    csrf_s = login(c, "siswa1")
    attempt_id = c.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s}
    ).json()["attempt"]["id"]
    # simpan draf: semua benar
    answers = [
        {"question_id": q["id"], "option_ids": opsi_ids(q, benar=True)} for q in full["questions"]
    ]
    res = c.put(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"answers": answers},
        headers={"x-csrf-token": csrf_s},
    )
    assert res.status_code == 200

    # mundurkan started_at melewati durasi -> GET attempt menutup otomatis & menilai draf
    db = SessionLocal()
    att = db.get(QuizAttempt, attempt_id)
    att.started_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    db.commit()
    db.close()

    res = c.get(f"/api/v1/attempts/{attempt_id}")
    body = res.json()
    assert body["attempt"]["status"] == "submitted"
    assert body["attempt"]["skor"] == 100.0


def test_esai_dinilai_guru(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf, enroll_ids=[siswa_id])
    quiz = buat_kuis(client, csrf, mid, tcml=ESAI_TCML, tipe="teks")
    full = client.get(f"/api/v1/quizzes/{quiz['id']}").json()
    assert full["questions"][0]["jawaban_referensi"].startswith("Tumbuhan")

    c = second_client()
    csrf_s = login(c, "siswa1")
    attempt_id = c.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s}
    ).json()["attempt"]["id"]
    answers = [
        {"question_id": q["id"], "jawaban_teks": f"Jawaban soal {q['id']}"} for q in full["questions"]
    ]
    res = c.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        json={"answers": answers},
        headers={"x-csrf-token": csrf_s},
    )
    assert res.json()["attempt"]["status"] == "submitted"
    assert res.json()["attempt"]["skor"] is None  # menunggu penilaian

    # guru menilai: Q1 bobot 3 -> poin 3, Q2 bobot 1 -> poin 0.5 => (3.5/4)*100 = 87.5
    grades = [
        {"question_id": full["questions"][0]["id"], "poin": 3},
        {"question_id": full["questions"][1]["id"], "poin": 0.5},
    ]
    res = client.post(
        f"/api/v1/attempts/{attempt_id}/grade",
        json={"grades": grades},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    assert res.json()["attempt"]["status"] == "graded"
    assert res.json()["attempt"]["skor"] == 87.5

    # poin melebihi bobot ditolak
    res = client.post(
        f"/api/v1/attempts/{attempt_id}/grade",
        json={"grades": [{"question_id": full["questions"][0]["id"], "poin": 99}]},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400

    # hasil & export
    results = client.get(f"/api/v1/quizzes/{quiz['id']}/results").json()
    assert results[0]["skor"] == 87.5
    res = client.get(f"/api/v1/quizzes/{quiz['id']}/export?format=csv")
    assert res.status_code == 200
    assert "siswa1" in res.text and "87.5" in res.text
    res = client.get(f"/api/v1/quizzes/{quiz['id']}/export?format=xlsx")
    assert res.status_code == 200
    assert "spreadsheet" in res.headers["content-type"]


def test_patch_soal_ditolak_bila_ada_attempt(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf, enroll_ids=[siswa_id])
    quiz = buat_kuis(client, csrf, mid)
    c = second_client()
    csrf_s = login(c, "siswa1")
    c.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s})
    res = client.patch(
        f"/api/v1/quizzes/{quiz['id']}",
        json={"teks_mentah": PG_TCML.replace("1 + 1", "2 + 2")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400


def test_kuis_dari_dan_ke_bank(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf)

    # simpan ke bank dulu lewat endpoint bank (Fase 2), lalu pakai dari bank
    res = client.post(
        "/api/v1/bank/quizzes",
        json={"judul": "Bank PG", "tipe": "pilihan_ganda", "teks_mentah": PG_TCML},
        headers={"x-csrf-token": csrf},
    )
    saved_id = res.json()["id"]
    res = client.post(
        f"/api/v1/meetings/{mid}/quizzes/from-bank/{saved_id}",
        json={"judul": "Dari Bank", "tipe": "pilihan_ganda", "teks_mentah": PG_TCML, "durasi_menit": 15},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    quiz = res.json()
    assert len(quiz["questions"]) == 2
    assert quiz["durasi_menit"] == 15

    # simpan kuis pertemuan ke bank
    res = client.post(
        f"/api/v1/quizzes/{quiz['id']}/save-to-bank",
        json={},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    rows = client.get("/api/v1/bank/quizzes").json()
    assert len(rows) == 2
