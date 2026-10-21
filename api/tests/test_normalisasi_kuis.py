"""Reproduksi & perbaikan error kuis AI (laporan Qualze 2026-10-21):
AI menulis format DATAR ([QUESTION] polos sebagai pembungkus, [OPTIONS]/
[ANSWER] berserakan di root) sehingga parser menolak dengan 'Pembungkus
soal wajib bernomor' + 'Blok tidak dikenal'. Normalisasi deterministik
memperbaikinya; mismatch tipe ditangani repair yang kini mengambil jenis
target dari brief job, bukan dari draf rusak."""

from tests.conftest import login, make_user
from tests.test_generate_pedagogi import buat_paket_lengkap, buat_setting, fake_ai

KUIS_DATAR = """[QUIZ]
[TITLE]Kuis Pecahan[/TITLE]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION]Apa arti pecahan 1/2?[/QUESTION]
[OPTIONS]
A. Satu dari dua bagian sama besar
B. Dua dari satu bagian utuh
[/OPTIONS]
[ANSWER]A[/ANSWER]
[QUESTION]Hasil 1/4 + 1/4 adalah?[/QUESTION]
[OPTIONS]
A. 1/2
B. 1/4
[/OPTIONS]
[ANSWER]A[/ANSWER]
[/QUIZ]"""

KUIS_DATAR_BERSARANG = """[QUIZ]
[TITLE]Kuis[/TITLE]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION]
Apa ibu kota Indonesia?
[OPTIONS]
A. Jakarta
B. Bandung
[/OPTIONS]
[ANSWER]A[/ANSWER]
[/QUESTION]
[/QUIZ]"""

KUIS_PG_SAH = """[QUIZ]
[TITLE]Kuis Pecahan[/TITLE]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]Apa arti pecahan 1/2?[/QUESTION]
[OPTIONS]
A. Satu dari dua bagian sama besar
B. Dua dari satu bagian utuh
[/OPTIONS]
[ANSWER]A[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""

KUIS_ESAI_SAH = """[QUIZ]
[TITLE]Kuis Esai[/TITLE]
[TYPE]essay[/TYPE]
[QUESTION 1]
[QUESTION]Jelaskan arti pecahan 1/2 dengan bahasamu sendiri.[/QUESTION]
[ANSWER]Pecahan 1/2 berarti satu dari dua bagian yang sama besar.[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""


def test_repro_error_format_datar():
    """Kondisi SEBELUM perbaikan: parser menolak format datar persis
    seperti error yang dilaporkan user."""
    from app.tcml.quiz import parse_quiz_v2

    res = parse_quiz_v2(KUIS_DATAR, expected_type="pilihan_ganda")
    assert not res["success"]
    pesan = " ".join(e["message"] for e in res["errors"])
    assert "wajib bernomor" in pesan
    assert "tidak dikenal" in pesan


def test_normalisasi_format_datar_menjadi_sah():
    from app.tcml.quiz import normalisasi_format_kuis, parse_quiz_v2

    baru = normalisasi_format_kuis(KUIS_DATAR)
    assert "[QUESTION 1]" in baru and "[QUESTION 2]" in baru
    res = parse_quiz_v2(baru, expected_type="pilihan_ganda")
    assert res["success"], res["errors"]
    assert len(res["content"]["questions"]) == 2
    assert res["content"]["questions"][0]["options"][0]["is_correct"] is True


def test_normalisasi_varian_bersarang_dan_penomoran():
    from app.tcml.quiz import normalisasi_format_kuis, parse_quiz_v2

    baru = normalisasi_format_kuis(KUIS_DATAR_BERSARANG)
    res = parse_quiz_v2(baru, expected_type="pilihan_ganda")
    assert res["success"], res["errors"]
    assert res["content"]["questions"][0]["pertanyaan"].startswith("Apa ibu kota")

    # Penomoran kacau (2 lalu 2) dinomori ulang 1, 2.
    kacau = KUIS_PG_SAH.replace("[QUESTION 1]", "[QUESTION 2]").replace("[/QUESTION 1]", "[/QUESTION 2]")
    kacau = kacau.replace("[/QUIZ]", """[QUESTION 2]
[QUESTION]Soal kedua?[/QUESTION]
[OPTIONS]
A. Ya
B. Tidak
[/OPTIONS]
[ANSWER]A[/ANSWER]
[/QUESTION 2]
[/QUIZ]""")
    baru2 = normalisasi_format_kuis(kacau)
    res2 = parse_quiz_v2(baru2, expected_type="pilihan_ganda")
    assert res2["success"], res2["errors"]
    assert len(res2["content"]["questions"]) == 2

    # Yang sudah kanonis & yang bukan kuis: tidak berubah.
    assert normalisasi_format_kuis(KUIS_PG_SAH) == KUIS_PG_SAH
    materi = "[MATERIAL]\n[TITLE]X[/TITLE]\n[/MATERIAL]"
    assert normalisasi_format_kuis(materi) == materi


def test_generate_kuis_datar_langsung_valid(client, monkeypatch):
    make_user("guru_datar", "guru")
    csrf = login(client, "guru_datar")
    buat_setting(client, csrf)
    pack = buat_paket_lengkap(client, csrf)
    fake_ai(monkeypatch, [KUIS_DATAR])
    res = client.post(
        "/api/v1/generate",
        json={"kind": "kuis_pg", "pack_id": pack["id"], "brief": {"topik": "Pecahan", "jumlah_soal": 2}},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    draft = res.json()["drafts"][0]
    assert draft["is_valid"], draft["errors"]
    assert "[QUESTION 1]" in draft["teks_mentah"]


def test_repair_mismatch_memakai_jenis_dari_job(client, monkeypatch):
    """Job meminta kuis ESAI; AI memberi PG (mismatch). Repair harus tetap
    menargetkan esai (dari brief job), bukan berbalik mengejar PG hanya
    karena draf terdeteksi PG."""
    make_user("guru_repair", "guru")
    csrf = login(client, "guru_repair")
    buat_setting(client, csrf)
    pack = buat_paket_lengkap(client, csrf)
    fake_ai(monkeypatch, [KUIS_PG_SAH])
    res = client.post(
        "/api/v1/generate",
        json={"kind": "kuis_esai", "pack_id": pack["id"], "brief": {"topik": "Pecahan", "jumlah_soal": 1}},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    draft = res.json()["drafts"][0]
    assert not draft["is_valid"]
    assert any("type mismatch" in e["message"] for e in draft["errors"])

    capture = []
    fake_ai(monkeypatch, [KUIS_ESAI_SAH], capture=capture)
    r2 = client.post(f"/api/v1/generate/drafts/{draft['id']}/repair", headers={"x-csrf-token": csrf})
    assert r2.status_code == 200, r2.text
    hasil = r2.json()
    assert hasil["is_valid"], hasil["errors"]
    assert hasil["tipe_quiz"] == "teks"
    # Prompt repair menyatakan tipe target secara eksplisit.
    assert "KONVERSI" in capture[0][1]["content"] or "esai" in capture[0][1]["content"].lower()
