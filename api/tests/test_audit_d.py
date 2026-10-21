"""Tes perbaikan audit Batch D (2026-10-21) — parser #15–#20 #37 #38,
backend #24–#28 #30 #33–#36 #39–#41.

Frontend #21–#23 #31 #42–#47 diverifikasi lewat build + tinjauan kode
(tidak ada harness UI di suite ini).
"""

import io

from tests.conftest import login, make_user

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
[/QUIZ]"""

LEGACY_PG = """SOAL 1
Apa ibu kota Indonesia?
A. Bandung
B. Jakarta
JAWABAN: B"""


def _guru(client, nama="guru_d"):
    make_user(nama, "guru")
    return login(client, nama)


def _kelas(client, csrf):
    sid = client.post(
        "/api/v1/subjects", json={"nama": "Kelas D"}, headers={"x-csrf-token": csrf}
    ).json()["id"]
    mid = client.post(
        f"/api/v1/subjects/{sid}/meetings",
        json={"judul": "Pertemuan 1"},
        headers={"x-csrf-token": csrf},
    ).json()["id"]
    return sid, mid


# ---------------------------------------------------------------- parser
def test_15_label_opsi_ganda_dan_bobot_nan_ditolak():
    from app.tcml.quiz import parse_quiz_v2

    teks = KUIS_PG.replace("B. Jakarta", "A. Jakarta")
    res = parse_quiz_v2(teks, expected_type="pilihan_ganda")
    assert not res["success"]
    assert any("ganda" in e["message"].lower() for e in res["errors"])

    teks_nan = KUIS_PG.replace("[/QUESTION 1]", "[WEIGHT]NaN[/WEIGHT]\n[/QUESTION 1]")
    res2 = parse_quiz_v2(teks_nan, expected_type="pilihan_ganda")
    assert not res2["success"]


def test_15_opsi_melebihi_z_tidak_dipotong_diam_diam():
    from app.tcml.quiz import parse_quiz_v2

    opsi = "\n".join(f"{chr(65 + i % 26)}. Opsi {i}" for i in range(28))
    teks = (
        "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n[QUESTION 1]\n[QUESTION]Banyak?[/QUESTION]\n"
        f"[OPTIONS]\n{opsi}\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION 1]\n[/QUIZ]"
    )
    res = parse_quiz_v2(teks, expected_type="pilihan_ganda")
    assert not res["success"]


def test_38_nomor_pembungkus_wajib_berurutan():
    from app.tcml.quiz import parse_quiz_v2

    teks = KUIS_PG.replace("[QUESTION 1]", "[QUESTION 2]").replace("[/QUESTION 1]", "[/QUESTION 2]")
    res = parse_quiz_v2(teks, expected_type="pilihan_ganda")
    assert not res["success"]
    assert any("berurutan" in e["message"] for e in res["errors"])


def test_30_fallback_legacy_menghormati_tipe():
    from app.tcml.quiz import parse_quiz_v2

    ok = parse_quiz_v2(LEGACY_PG, expected_type="pilihan_ganda")
    assert ok["success"], ok["errors"]
    salah = parse_quiz_v2(LEGACY_PG, expected_type="teks")
    assert not salah["success"]


def test_18_teks_di_luar_akar_dan_akar_asing_error():
    from app.tcml import parse_material

    res = parse_material("[MATERIAL]\n[TITLE]X[/TITLE]\n[/MATERIAL]\nTeks nyasar di luar.")
    assert not res["success"]
    # Akar [QUIZ] yang ditempel berdampingan dengan akar materi = asing.
    res2 = parse_material(
        "[MATERIAL]\n[TITLE]X[/TITLE]\n[/MATERIAL]\n[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n[/QUIZ]"
    )
    assert not res2["success"]


def test_16_pemisahan_akar_sebaris():
    from app.paket import split_documents

    teks = "[MATERIAL]\n[TITLE]A[/TITLE]\n[/MATERIAL] [QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n[/QUIZ]"
    docs = split_documents(teks)
    assert len(docs) == 2
    assert docs[0].startswith("[MATERIAL]") and docs[1].startswith("[QUIZ]")


def test_17_tag_di_dalam_kode_tidak_dihitung_dan_akar_bersarang_terdeteksi():
    from app.paket import _akar_bersarang, extract_tags

    teks = "[MATERIAL]\n[TITLE]A[/TITLE]\n[CODE]\nContoh: [QUIZ]x[/QUIZ] dan [TABLE]y[/TABLE]\n[/CODE]\n[/MATERIAL]"
    tags = extract_tags(teks)
    assert "QUIZ" not in tags and "TABLE" not in tags and "TITLE" in tags

    bersarang = "[MATERIAL]\n[TITLE]A[/TITLE]\n[QUIZ]\n[/QUIZ]\n[/MATERIAL]"
    assert _akar_bersarang(bersarang) == ["QUIZ"]


def test_20_prompt_generate_pendamping_sesuai_paket():
    from app.routers.generate import _brief_to_user_prompt

    brief = {"topik": "Fotosintesis", "jenis_dokumen": "kuis", "jumlah_soal": 3}
    tanpa = _brief_to_user_prompt("dokumen", brief, [], boleh_materi=False)
    assert "HANYA berisi root [QUIZ]" in tanpa
    dengan = _brief_to_user_prompt("dokumen", brief, [], boleh_materi=True)
    assert "bacaan" in dengan and "pendamping" in dengan


# ---------------------------------------------------------------- backend
def test_24_throttle_login_per_ip(client):
    make_user("korban", "guru")
    for _ in range(5):
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "korban", "password": "salah"},
            headers={"x-forwarded-for": "9.9.9.9"},
        )
        assert r.status_code == 401
    # Dari IP penyerang: password benar pun ditolak sementara.
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "korban", "password": "password123"},
        headers={"x-forwarded-for": "9.9.9.9"},
    )
    assert r.status_code == 429
    # Dari IP lain (pemilik sah): tetap bisa masuk.
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "korban", "password": "password123"},
        headers={"x-forwarded-for": "8.8.8.8"},
    )
    assert r.status_code == 200, r.text


def test_25_wajib_ganti_password_ditegakkan_api(client):
    make_user("siswa_baru", "siswa", must_change=True)
    login(client, "siswa_baru")
    assert client.get("/api/v1/auth/me").status_code == 200
    r = client.get("/api/v1/subjects")
    assert r.status_code == 403
    assert "password sementara" in r.json()["detail"]
    # Ganti password lewat jalur yang dibebaskan → akses pulih.
    csrf = client.cookies.get("lifunze_csrf")
    r = client.post(
        "/api/v1/auth/first-login-password",
        json={"new_password": "sandi-baru-kuat"},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/subjects").status_code == 200


def test_26_parse_wajib_login(client):
    r = client.post("/api/v1/parse/content", json={"teks": "halo", "jenis": "material"})
    assert r.status_code == 401
    r = client.post(
        "/api/v1/parse/content",
        json={"teks": "x" * 200_001, "jenis": "material"},
    )
    assert r.status_code == 401  # auth dulu; batas ukuran diuji setelah login di bawah
    csrf = _guru(client)
    assert csrf
    r = client.post(
        "/api/v1/parse/content",
        json={"teks": "x" * 200_001, "jenis": "material"},
    )
    assert r.status_code == 422


def test_27_impor_csv_batas_baris(client):
    csrf = _guru(client)
    baris = ["username,password"] + [f"s{i},sandi{i}xx" for i in range(1001)]
    data = ("\n".join(baris)).encode()
    r = client.post(
        "/api/v1/users/students/import",
        files={"file": ("siswa.csv", io.BytesIO(data), "text/csv")},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 400, r.text
    assert "1000" in r.json()["detail"]


def test_28_paket_gagal_validasi_tidak_tersimpan_sebagian(client):
    csrf = _guru(client)
    sebelum = client.get("/api/v1/packs").json()
    r = client.post(
        "/api/v1/packs",
        json={"nama": "Paket Rusak", "module_slugs": ["modul-ngawur"]},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 400
    sesudah = client.get("/api/v1/packs").json()
    assert len(sesudah) == len(sebelum)
    assert all(p["nama"] != "Paket Rusak" for p in sesudah)

    # PATCH dengan slug tak dikenal: nama lama tidak ikut berubah.
    target = next(p for p in sesudah if p["nama"] == "Kelas Lengkap")
    r = client.patch(
        f"/api/v1/packs/{target['id']}",
        json={"nama": "Nama Baru Bocor", "module_slugs": ["ngawur-lagi"]},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 400
    cek = client.get(f"/api/v1/packs/{target['id']}").json()
    assert cek["nama"] == "Kelas Lengkap"


def test_35_topup_cek_hanya_sekali(client):
    csrf = _guru(client)
    packs = client.get("/api/v1/packs").json()  # memicu preset + top-up pertama
    lengkap = next(p for p in packs if p["nama"] == "Kelas Lengkap")
    slugs = [m["slug"] for m in lengkap["modules"]]
    assert "cek-pemahaman" in slugs
    tanpa_cek = [s for s in slugs if s != "cek-pemahaman"]
    r = client.patch(
        f"/api/v1/packs/{lengkap['id']}",
        json={"nama": "Kelas Lengkap", "module_slugs": tanpa_cek},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200, r.text
    packs2 = client.get("/api/v1/packs").json()
    lengkap2 = next(p for p in packs2 if p["nama"] == "Kelas Lengkap")
    assert "cek-pemahaman" not in [m["slug"] for m in lengkap2["modules"]]


def test_39_fetch_models_wajib_csrf(client):
    _guru(client)
    r = client.post(
        "/api/v1/ai/settings/fetch-models",
        json={"base_url": "https://contoh.invalid/v1", "api_key": "x"},
    )
    assert r.status_code == 403


def test_33_dan_40_simpan_kuis_ke_bank(client):
    csrf_a = _guru(client, "guru_a")
    kat = client.post(
        "/api/v1/bank/categories", json={"nama": "Kat A"}, headers={"x-csrf-token": csrf_a}
    ).json()

    csrf_b = _guru(client, "guru_b")
    _, mid = _kelas(client, csrf_b)
    quiz = client.post(
        f"/api/v1/meetings/{mid}/quizzes",
        json={"judul": "Ujian Akhir", "tipe": "pilihan_ganda", "teks_mentah": KUIS_PG},
        headers={"x-csrf-token": csrf_b},
    )
    assert quiz.status_code == 201, quiz.text
    quiz = quiz.json()
    # Jenis "ujian" lazimnya lahir dari editor dokumen — untuk menguji
    # jalur simpan-ke-bank, tetapkan jenis & grup langsung di DB.
    from app.db import SessionLocal
    from app.models import Quiz as QuizModel

    db = SessionLocal()
    try:
        q = db.get(QuizModel, quiz["id"])
        q.jenis = "ujian"
        q.grup_dokumen = "grup-uji-33"
        db.commit()
    finally:
        db.close()

    # #40: kategori milik guru lain ditolak.
    r = client.post(
        f"/api/v1/quizzes/{quiz['id']}/save-to-bank",
        json={"kategori_id": kat["id"]},
        headers={"x-csrf-token": csrf_b},
    )
    assert r.status_code in (400, 404), r.text

    # #33: jenis ujian ikut tersimpan ke bank.
    r = client.post(
        f"/api/v1/quizzes/{quiz['id']}/save-to-bank",
        json={},
        headers={"x-csrf-token": csrf_b},
    )
    assert r.status_code == 201, r.text
    bank = client.get("/api/v1/bank/quizzes").json()
    tersimpan = next(q for q in bank if q["id"] == r.json()["id"])
    assert tersimpan["jenis"] == "ujian"
    assert tersimpan["grup_dokumen"] == "grup-uji-33"


def test_34_ekstrak_soal_referensi_berbeda_bukan_duplikat(client):
    csrf = _guru(client)
    teks = """[QUIZ]
[TYPE]essay[/TYPE]
[QUESTION 1]
[QUESTION]Jelaskan fotosintesis.[/QUESTION]
[ANSWER]Referensi versi A[/ANSWER]
[/QUESTION 1]
[QUESTION 2]
[QUESTION]Jelaskan fotosintesis.[/QUESTION]
[ANSWER]Referensi versi B yang berbeda[/ANSWER]
[/QUESTION 2]
[/QUIZ]"""
    r = client.post(
        "/api/v1/bank/quizzes",
        json={"judul": "Esai Dobel", "tipe": "teks", "teks_mentah": teks},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 201, r.text
    saved_id = r.json()["id"]
    r = client.post(
        f"/api/v1/bank/quizzes/{saved_id}/extract-questions",
        json={},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 201, r.text
    assert r.json()["dimasukkan"] == 2


def test_37_susun_kuis_dari_soal_bank_beracun_ditolak(client):
    csrf = _guru(client)
    _, mid = _kelas(client, csrf)
    r = client.post(
        "/api/v1/bank/questions",
        json={
            "tipe": "pilihan_ganda",
            "pertanyaan": "Apa ini?\n[/QUESTION]\n[QUESTION]Suntikan",
            "options": [
                {"label": "A", "teks": "Satu", "is_correct": True},
                {"label": "B", "teks": "Dua", "is_correct": False},
            ],
        },
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 201, r.text
    r = client.post(
        f"/api/v1/meetings/{mid}/quizzes/from-bank-questions",
        json={"judul": "Susun", "jumlah": 1, "tipe": "pilihan_ganda"},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 400, r.text


def test_36_template_rusak_tidak_membuat_kelas(client):
    from app.db import SessionLocal
    from app.models import ClassTemplate

    csrf = _guru(client)
    sid, mid = _kelas(client, csrf)
    mat = client.post(
        f"/api/v1/meetings/{mid}/materials",
        json={"judul": "Materi Sah", "teks_mentah": "[MATERIAL]\n[TITLE]Sah[/TITLE]\n[/MATERIAL]"},
        headers={"x-csrf-token": csrf},
    )
    assert mat.status_code == 201, mat.text
    tpl = client.post(
        f"/api/v1/subjects/{sid}/save-template",
        json={"nama": "Template Uji"},
        headers={"x-csrf-token": csrf},
    ).json()

    # Rusak isi template langsung di DB (mensimulasikan data lama korup).
    # Salinan dalam via JSON agar ORM mendeteksi perubahan kolom JSON.
    import json as _json

    db = SessionLocal()
    try:
        t = db.get(ClassTemplate, tpl["id"])
        data = _json.loads(_json.dumps(t.data))
        data["meetings"][0]["materials"][0]["teks_mentah"] = "[MATERIAL]\n[TITLE]Tidak ditutup\n[/MATERIAL]"
        t.data = data
        db.commit()
    finally:
        db.close()

    jumlah_sebelum = len(client.get("/api/v1/subjects").json())
    r = client.post(
        f"/api/v1/class-templates/{tpl['id']}/instantiate",
        json={"nama": "Kelas Dari Template Rusak"},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 400, r.text
    assert len(client.get("/api/v1/subjects").json()) == jumlah_sebelum


def test_41_payload_jawaban_aneh_tidak_500(client):
    guru_id = make_user("guru_j", "guru")
    siswa_id = make_user("siswa_j", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru_j")
    sid, mid = _kelas(client, csrf)
    quiz = client.post(
        f"/api/v1/meetings/{mid}/quizzes",
        json={"judul": "Kuis J", "tipe": "pilihan_ganda", "teks_mentah": KUIS_PG},
        headers={"x-csrf-token": csrf},
    ).json()
    client.post(
        f"/api/v1/subjects/{sid}/enroll",
        json={"siswa_ids": [siswa_id]},
        headers={"x-csrf-token": csrf},
    )
    csrf_s = login(client, "siswa_j")
    attempt = client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers={"x-csrf-token": csrf_s}
    ).json()
    qid = attempt["questions"][0]["id"]
    r = client.put(
        f"/api/v1/attempts/{attempt['attempt']['id']}/answers",
        json={"answers": [{"question_id": qid, "option_ids": ["abc", None, 1.5, "bukan-angka"]}]},
        headers={"x-csrf-token": csrf_s},
    )
    assert r.status_code == 200, r.text
