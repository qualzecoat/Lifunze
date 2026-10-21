"""Tes perbaikan audit 2026-10-21 Batch C: #6 (CEK di blok mentah),
#7 (blok asing di kuis), #8 (jenis & anti-duplikat Generate), #9 (pengaturan
kuis via bank), #11 (attempt setelah unenroll), #12 (pagar SSRF)."""

import pytest
from tests.conftest import login, make_user

PG = (
    "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
    "[QUESTION 1]\n[QUESTION]Ibu kota?[/QUESTION]\n"
    "[OPTIONS]\nA. Jakarta\nB. Bandung\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION 1]\n[/QUIZ]"
)

MATERI_CEK_DALAM_KODE = (
    "[MATERIAL]\n[TITLE]Contoh[/TITLE]\n"
    "[CODE]\n[CEK]\n[QUESTION]Ini contoh, bukan soal[/QUESTION]\n[/CEK]\n[/CODE]\n"
    "[CEK]\n[QUESTION]2+2?[/QUESTION]\n[OPTIONS]\nA. 3\nB. 4\n[/OPTIONS]\n[ANSWER]B[/ANSWER]\n[/CEK]\n"
    "[/MATERIAL]"
)


def _kelas(client, nama_guru="guruC", nama_siswa="siswaC"):
    guru = make_user(nama_guru, "guru")
    siswa = make_user(nama_siswa, "siswa", created_by_id=guru)
    csrf = login(client, nama_guru)
    h = {"x-csrf-token": csrf}
    sid = client.post("/api/v1/subjects", json={"nama": "K"}, headers=h).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers=h).json()["id"]
    client.post(f"/api/v1/subjects/{sid}/enroll", json={"siswa_ids": [siswa]}, headers=h)
    return {"guru": guru, "siswa": siswa, "csrf": csrf, "h": h, "sid": sid, "mid": mid}


def _kuis(client, k, **settings):
    body = {"judul": "Kuis", "tipe": "pilihan_ganda", "teks_mentah": PG}
    body.update(settings)
    r = client.post(f"/api/v1/meetings/{k['mid']}/quizzes", json=body, headers=k["h"])
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------- #6
def test_audit6_cek_dalam_blok_mentah_bukan_soal():
    from app.tcml import parse_material
    from app.tcml.cek import extract_ceks

    ceks, errors = extract_ceks(MATERI_CEK_DALAM_KODE)
    assert errors == []
    assert len(ceks) == 1  # hanya CEK sungguhan di luar [CODE]
    assert ceks[0]["pertanyaan"] == "2+2?"
    res = parse_material(MATERI_CEK_DALAM_KODE)
    assert res["success"], res["errors"]
    assert res["content"].count('data-cek-index') == 1


def test_audit6_contoh_cek_rusak_dalam_kode_tidak_menggagalkan():
    from app.tcml import parse_material

    teks = (
        "[MATERIAL]\n[TITLE]X[/TITLE]\n"
        "[CODE]\n[CEK]\n[QUESTION]Contoh rusak tanpa jawaban[/QUESTION]\n[/CEK]\n[/CODE]\n"
        "[/MATERIAL]"
    )
    res = parse_material(teks)
    assert res["success"], res["errors"]


# --------------------------------------------------------------------- #7
def test_audit7_blok_asing_di_kuis_error():
    from app.tcml.quiz import parse_quiz_v2

    dengan_cek = PG.replace("[/QUIZ]", "[CEK]\n[QUESTION]Sisipan?[/QUESTION]\n[/CEK]\n[/QUIZ]")
    res = parse_quiz_v2(dengan_cek)
    assert not res["success"]
    assert any("CEK" in e["message"] for e in res["errors"])

    tanpa_nomor = (
        "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
        "[QUESTION]\n[QUESTION]X?[/QUESTION]\n[OPTIONS]\nA. 1\nB. 2\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION]\n[/QUIZ]"
    )
    res2 = parse_quiz_v2(tanpa_nomor)
    assert not res2["success"]
    assert any("bernomor" in e["message"] for e in res2["errors"])

    blok_asing = PG.replace("[/QUIZ]", "[FOOBAR]isi[/FOOBAR]\n[/QUIZ]")
    res3 = parse_quiz_v2(blok_asing)
    assert not res3["success"]
    assert any("FOOBAR" in e["message"] for e in res3["errors"])

    assert parse_quiz_v2(PG)["success"]


# --------------------------------------------------------------------- #9
def test_audit9_pengaturan_kuis_roundtrip_bank(client):
    k = _kelas(client)
    q = _kuis(client, k, durasi_menit=45, acak_soal=True, acak_opsi=True, tampilkan_kunci=False)
    r = client.post(f"/api/v1/quizzes/{q['id']}/save-to-bank", json={}, headers=k["h"])
    assert r.status_code == 201, r.text
    saved = r.json()
    assert saved["durasi_menit"] == 45
    assert saved["acak_soal"] is True and saved["acak_opsi"] is True
    assert saved["tampilkan_kunci"] is False
    # Pakai kembali dari bank: pengaturan kembali, jendela tetap kosong.
    r2 = client.post(f"/api/v1/meetings/{k['mid']}/quizzes/from-bank/{saved['id']}", headers=k["h"])
    assert r2.status_code == 201, r2.text
    q2 = r2.json()
    assert q2["durasi_menit"] == 45
    assert q2["acak_soal"] is True and q2["acak_opsi"] is True
    assert q2["tampilkan_kunci"] is False
    assert q2["dibuka_pada"] is None and q2["ditutup_pada"] is None


# -------------------------------------------------------------------- #11
def test_audit11_attempt_terputus_setelah_unenroll(client):
    k = _kelas(client)
    q = _kuis(client, k)
    csrf_s = login(client, "siswaC")
    hs = {"x-csrf-token": csrf_s}
    att = client.post(f"/api/v1/quizzes/{q['id']}/attempts", headers=hs)
    assert att.status_code == 201, att.text
    attempt_id = att.json()["attempt"]["id"]
    # Guru mengeluarkan siswa dari kelas (login ulang: sesi client berpindah
    # ke siswa setelah start attempt).
    csrf_g = login(client, "guruC")
    r = client.delete(
        f"/api/v1/subjects/{k['sid']}/enroll/{k['siswa']}",
        headers={"x-csrf-token": csrf_g},
    )
    assert r.status_code == 200, r.text
    # Baca, simpan, submit: semua tertutup.
    hs2 = {"x-csrf-token": login(client, "siswaC")}
    assert client.get(f"/api/v1/attempts/{attempt_id}", headers=hs2).status_code == 403
    simpan = client.put(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"answers": []},
        headers=hs2,
    )
    assert simpan.status_code == 403
    kirim = client.post(f"/api/v1/attempts/{attempt_id}/submit", json={"answers": []}, headers=hs2)
    assert kirim.status_code == 403


# -------------------------------------------------------------------- #12
def test_audit12_pagar_ssrf_unit():
    from app.url_safety import UnsafeUrlError, assert_public_target, normalize_ai_base_url

    for buruk in (
        "http://127.0.0.1:8000/v1",
        "http://169.254.169.254/latest/meta-data",
        "https://localhost:11434/v1",
        "https://mesin.local/v1",
        "ftp://contoh.com/v1",
        "https://user:pass@api.contoh.com/v1",
        "http://[::1]/v1",
        "http://10.0.0.5/v1",
    ):
        with pytest.raises(UnsafeUrlError):
            normalize_ai_base_url(buruk)
    assert normalize_ai_base_url("https://openrouter.ai/api/v1/") == "https://openrouter.ai/api/v1"
    assert_public_target("https://8.8.8.8/v1")  # IP publik literal lolos


def test_audit12_setting_ke_ip_privat_ditolak_api(client):
    make_user("guruSSRF", "guru")
    csrf = login(client, "guruSSRF")
    r = client.post(
        "/api/v1/ai/settings",
        json={"nama": "Jahat", "base_url": "http://192.168.1.10:1234/v1", "api_key": "sk-x"},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 400, r.text


# --------------------------------------------------------------------- #8
DOK_UJIAN = (
    "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
    "[WARNING]Dilarang membuka catatan.[/WARNING]\n"
    "[QUESTION 1]\n[QUESTION]Ibu kota?[/QUESTION]\n"
    "[OPTIONS]\nA. Jakarta\nB. Bandung\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION 1]\n[/QUIZ]"
)


def _draf_dokumen_ujian(client, k):
    """Buat draf dokumen jenis UJIAN langsung di DB (meniru hasil generate)."""
    from app.db import SessionLocal
    from app.models import ContentDraft, GenerationJob

    db = SessionLocal()
    job = GenerationJob(
        user_id=k["guru"], pack_id=None, ai_setting_id=None,
        brief={"kind": "dokumen", "jenis_dokumen": "ujian", "topik": "Geografi"},
        status="done",
    )
    db.add(job)
    db.flush()
    d = ContentDraft(
        generation_job_id=job.id, user_id=k["guru"], jenis="dokumen",
        judul="Ujian Geografi", teks_mentah=DOK_UJIAN, is_valid=True, status="draft",
    )
    db.add(d)
    db.commit()
    did = d.id
    db.close()
    return did


def test_audit8_publish_dokumen_memakai_jenis_dan_anti_duplikat(client):
    k = _kelas(client)
    did = _draf_dokumen_ujian(client, k)
    r = client.post(
        f"/api/v1/generate/drafts/{did}/publish",
        json={"meeting_id": k["mid"]},
        headers=k["h"],
    )
    assert r.status_code == 201, r.text
    grup = r.json()["grup"]
    doc = client.get(f"/api/v1/documents/{grup}", headers=k["h"]).json()
    assert doc["jenis"] == "ujian"
    # Preset ujian: acak soal & opsi menyala.
    assert doc["pengaturan_kuis"]["acak_soal"] is True
    assert doc["pengaturan_kuis"]["acak_opsi"] is True
    # Terbit kedua dari draf yang sama ditolak (anti duplikat).
    r2 = client.post(
        f"/api/v1/generate/drafts/{did}/publish",
        json={"meeting_id": k["mid"]},
        headers=k["h"],
    )
    assert r2.status_code == 400, r2.text
    r3 = client.post(
        f"/api/v1/generate/drafts/{did}/save-bank",
        json={},
        headers=k["h"],
    )
    assert r3.status_code == 400, r3.text


def test_audit8_save_bank_dokumen_memakai_jenis(client):
    k = _kelas(client, "guruC2", "siswaC2")
    did = _draf_dokumen_ujian(client, k)
    r = client.post(
        f"/api/v1/generate/drafts/{did}/save-bank",
        json={},
        headers=k["h"],
    )
    assert r.status_code == 201, r.text
    grup = r.json()["grup"]
    doc = client.get(f"/api/v1/bank/documents/{grup}", headers=k["h"]).json()
    assert doc["jenis"] == "ujian"
    assert doc["quizzes"][0]["acak_soal"] is True
