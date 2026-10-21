"""Tes Cek Pemahaman [CEK] + blok pengantar kuis + generate per jenis."""

import pytest

from app.tcml import parse_material
from app.tcml.cek import cek_untuk_siswa, extract_ceks
from app.tcml.quiz import parse_quiz_v2
from app.tcml.structure import document_to_blocks
from tests.conftest import login, make_user

MATERI_CEK = """[MATERIAL]
[TITLE]Mengenal Word[/TITLE]
[PARAGRAPH]Ctrl+V untuk menempel teks.[/PARAGRAPH]
[CEK]
[QUESTION]Apa fungsi Ctrl + V?[/QUESTION]
[OPTIONS]
A. Menyalin teks
B. Menempel teks
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/CEK]
[CEK]
[TYPE]essay[/TYPE]
[QUESTION]Mengapa menyimpan berkala itu penting?[/QUESTION]
[ANSWER]Agar pekerjaan tidak hilang saat listrik padam.[/ANSWER]
[/CEK]
[/MATERIAL]"""


def test_cek_terekstrak_dan_render_tanpa_kunci():
    res = parse_material(MATERI_CEK)
    assert res["success"], res["errors"]
    assert 'data-cek-index="0"' in res["content"]
    assert 'data-cek-index="1"' in res["content"]
    # Kunci & referensi TIDAK boleh bocor ke HTML hasil render.
    assert "Menempel teks" not in res["content"]
    assert "listrik padam" not in res["content"]
    ceks, errors = extract_ceks(MATERI_CEK)
    assert not errors and len(ceks) == 2
    assert ceks[0]["tipe"] == "pilihan_ganda"
    assert [o["label"] for o in ceks[0]["options"] if o["is_correct"]] == ["B"]
    assert ceks[1]["tipe"] == "teks"
    # Bentuk siswa tidak memuat kunci sama sekali.
    aman = cek_untuk_siswa(ceks[0], 0)
    assert all("is_correct" not in o for o in aman["options"])


def test_cek_tidak_valid_ditolak():
    tanpa_kunci = MATERI_CEK.replace("[ANSWER]B[/ANSWER]", "")
    assert not parse_material(tanpa_kunci)["success"]
    esai_tanpa_referensi = MATERI_CEK.replace(
        "[ANSWER]Agar pekerjaan tidak hilang saat listrik padam.[/ANSWER]", ""
    )
    assert not parse_material(esai_tanpa_referensi)["success"]


def test_cek_terpetakan_ke_mode_blok():
    out = document_to_blocks(MATERI_CEK)
    assert out["bisa_formulir"], out["alasan"]
    jenis = [b["jenis"] for b in out["blocks"]]
    assert "cek-pg" in jenis and "cek-esai" in jenis
    pg = next(b for b in out["blocks"] if b["jenis"] == "cek-pg")
    assert pg["opsi"][1] == {"teks": "Menempel teks", "benar": True}
    esai = next(b for b in out["blocks"] if b["jenis"] == "cek-esai")
    assert "listrik padam" in esai["referensi"]


def test_kuis_blok_pengantar():
    teks = (
        "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
        "Selamat datang di kuis ini.\n"
        "[NOTE]Dua soal saja.[/NOTE]\n"
        "[QUESTION 1]\n[QUESTION]Fungsi Ctrl+C?[/QUESTION]\n"
        "[OPTIONS]\nA. Menyalin\nB. Menempel\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION 1]\n"
        "[HINT]C untuk Copy.[/HINT]\n"
        "[QUESTION 2]\n[QUESTION]Fungsi Ctrl+V?[/QUESTION]\n"
        "[OPTIONS]\nA. Menyalin\nB. Menempel\n[/OPTIONS]\n[ANSWER]B[/ANSWER]\n[/QUESTION 2]\n[/QUIZ]"
    )
    res = parse_quiz_v2(teks)
    assert res["success"], res["errors"]
    assert len(res["content"]["questions"]) == 2
    items = res["content"]["items"]
    assert [i["jenis"] for i in items] == ["konten", "konten", "soal", "konten", "soal"]
    assert items[0]["tipe"] == "paragraf"
    assert items[3]["teks"] == "C untuk Copy."


# ----------------------------------------------------------------- API
@pytest.fixture()
def kelas_dengan_cek(client):
    """Guru + kelas + siswa terdaftar + materi ber-[CEK]."""

    guru_id = make_user("gurucek", "guru")
    siswa_id = make_user("siswacek", "siswa", created_by_id=guru_id)
    csrf = login(client, "gurucek")
    h = {"x-csrf-token": csrf}
    kelas = client.post(
        "/api/v1/subjects", json={"nama": "Kelas Cek"}, headers=h
    ).json()
    pertemuan = client.post(
        f"/api/v1/subjects/{kelas['id']}/meetings",
        json={"judul": "Pertemuan 1"},
        headers=h,
    ).json()
    client.post(
        f"/api/v1/subjects/{kelas['id']}/enroll",
        json={"siswa_ids": [siswa_id]},
        headers=h,
    )
    materi = client.post(
        f"/api/v1/meetings/{pertemuan['id']}/materials",
        json={"judul": "Word Dasar", "teks_mentah": MATERI_CEK},
        headers=h,
    ).json()
    return {"guru_id": guru_id, "siswa_id": siswa_id, "kelas": kelas, "materi": materi, "csrf_guru": csrf}


def test_alur_jawab_cek(client, kelas_dengan_cek):
    k = kelas_dengan_cek
    mid = k["materi"]["id"]
    csrf = login(client, "siswacek")
    h = {"x-csrf-token": csrf}

    # Payload siswa: ada daftar cek, tanpa kunci.
    got = client.get(f"/api/v1/materials/{mid}").json()
    daftar = got["cek"]["daftar"]
    assert len(daftar) == 2
    assert all("kunci" not in d and "jawaban_referensi" not in d for d in daftar)
    assert daftar[0]["jawabanku"] is None

    # Jawab PG salah dulu -> benar False, skor 0.
    r = client.post(f"/api/v1/materials/{mid}/cek/0/jawab", json={"jawaban": "A"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["benar"] is False
    assert r.json()["kunci"] == ["B"]

    # Ulangi dengan benar -> nilai terakhir yang dipakai.
    r = client.post(f"/api/v1/materials/{mid}/cek/0/jawab", json={"jawaban": "B"}, headers=h)
    assert r.json()["benar"] is True
    assert r.json()["skor"]["persen"] == 100.0

    # Esai: referensi hanya terbuka setelah menjawab.
    r = client.post(
        f"/api/v1/materials/{mid}/cek/1/jawab",
        json={"jawaban": "Supaya tidak hilang kalau mati lampu."},
        headers=h,
    )
    assert r.status_code == 200
    assert "listrik padam" in r.json()["jawaban_referensi"]
    assert r.json()["benar"] is None

    # Jawabanku tersimpan saat GET ulang.
    got = client.get(f"/api/v1/materials/{mid}").json()
    assert got["cek"]["daftar"][0]["jawabanku"]["jawaban"] == "B"
    assert got["cek"]["skor"]["persen"] == 100.0


def test_hasil_cek_untuk_guru(client, kelas_dengan_cek):
    k = kelas_dengan_cek
    mid = k["materi"]["id"]
    csrf = login(client, "siswacek")
    client.post(
        f"/api/v1/materials/{mid}/cek/0/jawab",
        json={"jawaban": "B"},
        headers={"x-csrf-token": csrf},
    )
    # Guru membuka ringkasan hasil.
    login(client, "gurucek")
    r = client.get(f"/api/v1/materials/{mid}/cek/hasil")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_cek"] == 2
    baris = next(s for s in data["siswa"] if s["nama"] == "Siswacek")
    assert baris["terjawab"] == 1
    assert baris["skor_persen"] == 100.0
    # Siswa tidak boleh membuka ringkasan kelas.
    login(client, "siswacek")
    assert client.get(f"/api/v1/materials/{mid}/cek/hasil").status_code == 403


def _fake_ai_rekam(monkeypatch, output: str) -> dict:
    prompts: dict = {}

    def _fake(setting, messages, temperature=0.7):
        prompts["system"] = messages[0]["content"]
        prompts["user"] = messages[1]["content"]
        return output

    monkeypatch.setattr("app.routers.generate.chat_completion", _fake)
    return prompts


def _setting_ai(client, csrf):
    res = client.post(
        "/api/v1/ai/settings",
        json={
            "nama": "Tes",
            "base_url": "https://api.contoh.com/v1",
            "api_key": "sk-tes-123456",
            "model": "model-tes",
            "is_default": True,
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text


def _paket_lengkap(client):
    packs = client.get("/api/v1/packs").json()
    return next(p for p in packs if p["nama"] == "Kelas Lengkap")


def test_generate_dokumen_jenis_materi_memakai_cek(client, monkeypatch):
    """Prompt generate jenis materi menyebut [CEK] bila paket memuat modulnya,
    dan draf campuran (bacaan + CEK) lolos validasi bundle."""

    make_user("gurucek2", "guru")
    csrf = login(client, "gurucek2")
    h = {"x-csrf-token": csrf}
    _setting_ai(client, csrf)
    lengkap = _paket_lengkap(client)
    # Paket Kelas Lengkap kini memuat modul cek-pemahaman.
    modul = {m["slug"] for m in lengkap["modules"]}
    assert "cek-pemahaman" in modul

    prompts = _fake_ai_rekam(monkeypatch, MATERI_CEK)
    r = client.post(
        "/api/v1/generate",
        json={
            "kind": "dokumen",
            "pack_id": lengkap["id"],
            "brief": {"topik": "Microsoft Word dasar", "jenis_dokumen": "materi"},
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    assert "[CEK]" in prompts["user"]
    draf = r.json()["drafts"][0]
    assert draf["is_valid"], draf["errors"]


def test_generate_dokumen_jenis_ujian_tanpa_hint(client, monkeypatch):

    make_user("gurucek3", "guru")
    csrf = login(client, "gurucek3")
    h = {"x-csrf-token": csrf}
    _setting_ai(client, csrf)
    lengkap = _paket_lengkap(client)
    kuis = (
        "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
        "[WARNING]Ujian tertutup.[/WARNING]\n"
        "[QUESTION 1]\n[QUESTION]Fungsi Ctrl+C?[/QUESTION]\n"
        "[OPTIONS]\nA. Menyalin\nB. Menempel\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION 1]\n[/QUIZ]"
    )
    prompts = _fake_ai_rekam(monkeypatch, kuis)
    r = client.post(
        "/api/v1/generate",
        json={
            "kind": "dokumen",
            "pack_id": lengkap["id"],
            "brief": {"topik": "Ujian Word", "jenis_dokumen": "ujian", "jumlah_soal": 1},
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    assert "JANGAN menyelipkan [HINT]" in prompts["user"]
    draf = r.json()["drafts"][0]
    assert draf["is_valid"], draf["errors"]
