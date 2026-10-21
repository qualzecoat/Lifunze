"""Tes perbaikan audit 2026-10-21 Batch B: #4 (integritas nilai CEK),
#5 (hapus bermuatan jejak siswa), #10/#32 (jendela & pengaturan kuis),
#29 (satu attempt aktif per siswa)."""

from datetime import datetime, timedelta, timezone

import pytest
from tests.conftest import login, make_user

MATERI_CEK = (
    "[MATERIAL]\n[TITLE]M[/TITLE]\n[PARAGRAPH]Isi awal.[/PARAGRAPH]\n"
    "[CEK]\n[QUESTION]2+2?[/QUESTION]\n[OPTIONS]\nA. 3\nB. 4\n[/OPTIONS]\n"
    "[ANSWER]B[/ANSWER]\n[/CEK]\n[/MATERIAL]"
)
PG = (
    "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n"
    "[QUESTION 1]\n[QUESTION]Ibu kota?[/QUESTION]\n"
    "[OPTIONS]\nA. Jakarta\nB. Bandung\n[/OPTIONS]\n[ANSWER]A[/ANSWER]\n[/QUESTION 1]\n[/QUIZ]"
)


def _kelas(client, nama_guru="guruB", nama_siswa="siswaB"):
    guru = make_user(nama_guru, "guru")
    siswa = make_user(nama_siswa, "siswa", created_by_id=guru)
    csrf = login(client, nama_guru)
    h = {"x-csrf-token": csrf}
    sid = client.post("/api/v1/subjects", json={"nama": "K"}, headers=h).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers=h).json()["id"]
    client.post(f"/api/v1/subjects/{sid}/enroll", json={"siswa_ids": [siswa]}, headers=h)
    return {"guru": guru, "siswa": siswa, "csrf": csrf, "h": h, "sid": sid, "mid": mid}


def _materi_cek(client, k):
    r = client.post(
        f"/api/v1/meetings/{k['mid']}/materials",
        json={"judul": "M", "teks_mentah": MATERI_CEK},
        headers=k["h"],
    )
    assert r.status_code == 201, r.text
    return r.json()


def _jawab_cek_benar(client, k, mat_id):
    csrf_s = login(client, "siswaB")
    r = client.post(
        f"/api/v1/materials/{mat_id}/cek/0/jawab",
        json={"jawaban": "B"},
        headers={"x-csrf-token": csrf_s},
    )
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------- #4
def test_audit4_cek_terkunci_setelah_dijawab(client):
    k = _kelas(client)
    m = _materi_cek(client, k)
    hasil = _jawab_cek_benar(client, k, m["id"])
    assert hasil["skor"]["persen"] == 100.0
    csrf_g = login(client, "guruB")
    h = {"x-csrf-token": csrf_g}
    # Mengubah isi soal sisipan -> ditolak.
    teks_ubah_soal = MATERI_CEK.replace("2+2?", "3+3?")
    r = client.patch(
        f"/api/v1/materials/{m['id']}",
        json={"judul": "M", "teks_mentah": teks_ubah_soal},
        headers=h,
    )
    assert r.status_code == 400, r.text
    # Mengedit paragraf di luar [CEK] -> boleh.
    teks_ubah_isi = MATERI_CEK.replace("Isi awal.", "Isi yang diperbarui.")
    r2 = client.patch(
        f"/api/v1/materials/{m['id']}",
        json={"judul": "M", "teks_mentah": teks_ubah_isi},
        headers=h,
    )
    assert r2.status_code == 200, r2.text


def test_audit4_skor_membatasi_jawaban_basi():
    from app.models import CekAnswer
    from app.routers.materials import _skor_cek

    ceks = [{"tipe": "pilihan_ganda", "bobot": 2.0}, {"tipe": "essay", "bobot": 1.0}]
    basi_indeks = CekAnswer(material_id=1, siswa_id=1, cek_index=9, tipe="pilihan_ganda", jawaban="A", skor=50.0)
    basi_tipe = CekAnswer(material_id=1, siswa_id=1, cek_index=1, tipe="pilihan_ganda", jawaban="A", skor=50.0)
    sah = CekAnswer(material_id=1, siswa_id=1, cek_index=0, tipe="pilihan_ganda", jawaban="B", skor=2.0)
    skor = _skor_cek(ceks, {9: basi_indeks, 1: basi_tipe, 0: sah})
    assert skor == {"diperoleh": 2.0, "maksimal": 2.0, "persen": 100.0}


# --------------------------------------------------------------------- #5
def test_audit5_hapus_materi_dan_kelas_berjejak_siswa(client):
    k = _kelas(client)
    m = _materi_cek(client, k)
    csrf_s = login(client, "siswaB")
    hs = {"x-csrf-token": csrf_s}
    client.post(f"/api/v1/materials/{m['id']}/read", headers=hs)  # MaterialRead
    _jawab_cek_benar(client, k, m["id"])  # CekAnswer
    csrf_g = login(client, "guruB")
    r = client.delete(f"/api/v1/materials/{m['id']}", headers={"x-csrf-token": csrf_g})
    assert r.status_code == 200, r.text
    # Hapus kelas yang masih punya pengumuman & pertemuan juga harus berhasil.
    client.post(
        f"/api/v1/subjects/{k['sid']}/announcements",
        json={"judul": "Info", "isi": "Halo"},
        headers={"x-csrf-token": csrf_g},
    )
    r2 = client.delete(f"/api/v1/subjects/{k['sid']}", headers={"x-csrf-token": csrf_g})
    assert r2.status_code == 200, r2.text


# ---------------------------------------------------------------- #10/#32
def _kuis(client, k, **settings):
    body = {"judul": "Kuis", "tipe": "pilihan_ganda", "teks_mentah": PG}
    body.update(settings)
    r = client.post(f"/api/v1/meetings/{k['mid']}/quizzes", json=body, headers=k["h"])
    assert r.status_code == 201, r.text
    return r.json()


def test_audit10_jendela_menutup_attempt_yang_berjalan(client):
    k = _kelas(client)
    nanti = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    q = _kuis(client, k, ditutup_pada=nanti)
    csrf_s = login(client, "siswaB")
    hs = {"x-csrf-token": csrf_s}
    att = client.post(f"/api/v1/quizzes/{q['id']}/attempts", headers=hs)
    assert att.status_code == 201, att.text
    attempt_id = att.json()["attempt"]["id"]
    qid = att.json()["questions"][0]["id"]
    oid = att.json()["questions"][0]["options"][0]["id"]
    # Jendela ditutup dari sisi DB (mensimulasikan waktu berlalu; API memang
    # mengunci perubahan pengaturan setelah ada attempt).
    from app.db import SessionLocal
    from app.models import Quiz

    db = SessionLocal()
    quiz = db.get(Quiz, q["id"])
    quiz.ditutup_pada = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
    db.close()
    # Simpan jawaban setelah tutup -> 400 & attempt difinalisasi.
    r = client.put(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"answers": [{"question_id": qid, "option_ids": [oid]}]},
        headers=hs,
    )
    assert r.status_code == 400, r.text
    lihat = client.get(f"/api/v1/attempts/{attempt_id}", headers=hs)
    assert lihat.json()["attempt"]["status"] == "submitted"


def test_audit10_pengaturan_terkunci_setelah_attempt(client):
    k = _kelas(client)
    q = _kuis(client, k)
    csrf_s = login(client, "siswaB")
    client.post(f"/api/v1/quizzes/{q['id']}/attempts", headers={"x-csrf-token": csrf_s})
    csrf_g = login(client, "guruB")
    h = {"x-csrf-token": csrf_g}
    r = client.patch(f"/api/v1/quizzes/{q['id']}", json={"durasi_menit": 30}, headers=h)
    assert r.status_code == 400, r.text
    r2 = client.patch(f"/api/v1/quizzes/{q['id']}", json={"judul": "Judul Baru"}, headers=h)
    assert r2.status_code == 200, r2.text


# --------------------------------------------------------------------- #29
def test_audit29_indeks_unik_attempt_aktif():
    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.models import QuizAttempt

    db = SessionLocal()
    db.add(QuizAttempt(quiz_id=999001, siswa_id=999001, status="in_progress"))
    db.commit()
    db.add(QuizAttempt(quiz_id=999001, siswa_id=999001, status="in_progress"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # Attempt kedua yang sudah submitted tidak dibatasi indeks parsial.
    db.add(QuizAttempt(quiz_id=999001, siswa_id=999001, status="submitted"))
    db.commit()
    db.query(QuizAttempt).filter(QuizAttempt.quiz_id == 999001).delete()
    db.commit()
    db.close()
