"""Test dokumen terpadu: split teks gabungan, CRUD pasangan materi+kuis,
pagar integritas, dan pengumpulan untuk dokumen berjenis Tugas."""

from conftest import login, make_user
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import QuizAttempt
from app.tcml.document import split_document

MATERI = "[MATERIAL]\n[TITLE]Bab Gabungan[/TITLE]\nIsi bacaan.\n[/MATERIAL]"

PG = """[QUIZ]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]1 + 1 = ?[/QUESTION]
[OPTIONS]
A. 1
B. 2
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""

ESAI = """[QUIZ]
[TYPE]essay[/TYPE]
[QUESTION 1]
[QUESTION]Jelaskan jawabanmu.[/QUESTION]
[ANSWER]Referensi guru.[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""


def setup_kelas(client, csrf, enroll_ids=()):
    sid = client.post(
        "/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}
    ).json()["id"]
    mid = client.post(
        f"/api/v1/subjects/{sid}/meetings",
        json={"judul": "P1"},
        headers={"x-csrf-token": csrf},
    ).json()["id"]
    if enroll_ids:
        client.post(
            f"/api/v1/subjects/{sid}/enroll",
            json={"siswa_ids": list(enroll_ids)},
            headers={"x-csrf-token": csrf},
        )
    return sid, mid


def buat_dokumen(client, csrf, mid, **kw):
    body = {
        "judul": "Dokumen 1",
        "jenis": "materi",
        "teks_materi": MATERI,
        "teks_kuis_pg": PG,
        "teks_kuis_esai": ESAI,
        "pengaturan_kuis": {"acak_soal": True},
    }
    body.update(kw)
    return client.post(
        f"/api/v1/meetings/{mid}/documents", json=body, headers={"x-csrf-token": csrf}
    )


# ------------------------------------------------------------------ split
def test_split_dokumen_gabungan():
    parts = split_document(MATERI + "\n" + PG + "\n" + ESAI)
    assert parts["errors"] == []
    assert parts["materi"].startswith("[MATERIAL]")
    assert parts["kuis_pg"].startswith("[QUIZ]")
    assert parts["kuis_esai"].startswith("[QUIZ]")


def test_split_dua_materi_error():
    parts = split_document(MATERI + "\n" + MATERI)
    assert parts["materi"] is not None
    assert any("lebih dari satu" in e["message"] for e in parts["errors"])


def test_split_teks_luar_akar_error():
    parts = split_document("halo dunia\n" + MATERI)
    assert any("di luar akar" in e["message"] for e in parts["errors"])


# ------------------------------------------------------------------ CRUD
def test_buat_dokumen_lengkap(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf)
    res = buat_dokumen(client, csrf, mid)
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["material"]["judul"] == "Dokumen 1"
    assert len(doc["quizzes"]) == 2
    tipes = {q["tipe"] for q in doc["quizzes"]}
    assert tipes == {"pilihan_ganda", "teks"}
    assert all(q["grup_dokumen"] == doc["grup"] for q in doc["quizzes"])
    assert all(q["acak_soal"] is True for q in doc["quizzes"])
    assert doc["material"]["grup_dokumen"] == doc["grup"]

    # info pasangan dua arah
    mat = client.get(f"/api/v1/materials/{doc['material']['id']}").json()
    assert len(mat["dokumen_kuis"]) == 2
    quiz_pg = next(q for q in doc["quizzes"] if q["tipe"] == "pilihan_ganda")
    assert quiz_pg["dokumen_materi_id"] == doc["material"]["id"]
    assert len(quiz_pg["questions"]) == 1


def test_buat_dokumen_sebagian_dan_kosong(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf)
    res = buat_dokumen(client, csrf, mid, teks_materi=None, teks_kuis_esai=None)
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["material"] is None and len(doc["quizzes"]) == 1

    res = buat_dokumen(
        client, csrf, mid, teks_materi=None, teks_kuis_pg=None, teks_kuis_esai=None
    )
    assert res.status_code == 400


def test_patch_dokumen_hapus_dan_tambah_bagian(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf)
    doc = buat_dokumen(client, csrf, mid).json()
    # hapus bagian esai, ubah teks materi
    res = client.patch(
        f"/api/v1/documents/{doc['grup']}",
        json={
            "judul": "Dokumen 1",
            "jenis": "kuis",
            "teks_materi": MATERI.replace("Bab Gabungan", "Bab Revisi"),
            "teks_kuis_pg": PG,
            "teks_kuis_esai": None,
            "pengaturan_kuis": {},
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200, res.text
    doc2 = res.json()
    assert len(doc2["quizzes"]) == 1
    assert doc2["jenis"] == "kuis"
    assert "Bab Revisi" in doc2["material"]["teks_mentah"]


def test_patch_kuis_sudah_dikerjakan_ditolak(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf, [siswa_id])
    doc = buat_dokumen(client, csrf, mid, teks_materi=None, teks_kuis_esai=None).json()
    quiz_id = doc["quizzes"][0]["id"]
    db = SessionLocal()
    db.add(QuizAttempt(quiz_id=quiz_id, siswa_id=siswa_id, status="submitted"))
    db.commit()
    db.close()
    res = client.patch(
        f"/api/v1/documents/{doc['grup']}",
        json={
            "judul": "Dokumen 1",
            "jenis": "kuis",
            "teks_kuis_pg": PG.replace("1 + 1", "2 + 2"),
            "pengaturan_kuis": {},
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400
    assert "sudah ada siswa" in res.json()["detail"]


def test_hapus_dokumen(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf)
    doc = buat_dokumen(client, csrf, mid).json()
    res = client.delete(
        f"/api/v1/documents/{doc['grup']}", headers={"x-csrf-token": csrf}
    )
    assert res.status_code == 200
    assert client.get(f"/api/v1/documents/{doc['grup']}").status_code == 404
    assert client.get(f"/api/v1/materials/{doc['material']['id']}").status_code == 404


# ------------------------------------------------------------------ jenis Tugas
def test_dokumen_jenis_tugas_bisa_pengumpulan(client):
    guru_id = make_user("guru1", "guru")
    siswa_id = make_user("siswa1", "siswa", created_by_id=guru_id)
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf, [siswa_id])
    doc = buat_dokumen(
        client, csrf, mid,
        jenis="tugas", teks_kuis_pg=None, teks_kuis_esai=None,
        tenggat="2026-11-01T23:59:00+07:00",
    ).json()
    mat_id = doc["material"]["id"]
    assert doc["tenggat"] is not None

    c = TestClient(app)
    csrf_s = login(c, "siswa1")
    info = c.get(f"/api/v1/materials/{mat_id}/submissions").json()
    assert info["is_project"] is True
    res = c.post(
        f"/api/v1/materials/{mat_id}/submissions",
        files={"file": ("tugas.txt", b"isi tugas", "text/plain")},
        headers={"x-csrf-token": csrf_s},
    )
    assert res.status_code == 201, res.text


# ------------------------------------------------------------------ bank dokumen
def _bank_doc(client, csrf, **kw):
    body = {
        "judul": "Dok Bank",
        "jenis": "materi",
        "teks_materi": MATERI,
        "teks_kuis_pg": PG,
        "teks_kuis_esai": None,
    }
    body.update(kw)
    return client.post("/api/v1/bank/documents", json=body, headers={"x-csrf-token": csrf})


def test_bank_dokumen_siklus_penuh(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf)
    res = _bank_doc(client, csrf)
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["material"]["judul"] == "Dok Bank"
    assert len(doc["quizzes"]) == 1
    assert doc["quizzes"][0]["jumlah_soal"] == 1

    # daftar bank memuat field grup pada kedua daftar lama
    mats = client.get("/api/v1/bank/materials").json()
    assert mats[0]["grup_dokumen"] == doc["grup"]
    # pakai ke kelas -> pasangan baru dengan grup berbeda
    res = client.post(
        f"/api/v1/bank/documents/{doc['grup']}/use",
        json={"meeting_id": mid},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    terpasang = res.json()
    assert terpasang["grup"] != doc["grup"]
    assert terpasang["material"] is not None and len(terpasang["quizzes"]) == 1

    # salin dokumen bank (grup baru lagi), lalu hapus salinannya
    res = client.post(
        f"/api/v1/bank/documents/{doc['grup']}/copy", headers={"x-csrf-token": csrf}
    )
    assert res.status_code == 201, res.text
    salinan = res.json()
    assert salinan["grup"] != doc["grup"]
    res = client.delete(
        f"/api/v1/bank/documents/{salinan['grup']}", headers={"x-csrf-token": csrf}
    )
    assert res.status_code == 200
    assert client.get(f"/api/v1/bank/documents/{salinan['grup']}").status_code == 404


def test_dokumen_kelas_simpan_ke_bank_sekali(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _, mid = setup_kelas(client, csrf)
    doc = buat_dokumen(client, csrf, mid, teks_kuis_esai=None).json()
    res = client.post(
        f"/api/v1/documents/{doc['grup']}/save-to-bank",
        json={},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    bank_grup = res.json()["grup"]
    tersimpan = client.get(f"/api/v1/bank/documents/{bank_grup}").json()
    assert tersimpan["material"] is not None and len(tersimpan["quizzes"]) == 1
    # kedua kali -> ditolak (aturan penanda asal)
    res = client.post(
        f"/api/v1/documents/{doc['grup']}/save-to-bank",
        json={},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400
    # detail kelas menandai di_bank untuk kedua bagian
    detail = client.get(
        f"/api/v1/subjects/{client.get(f'/api/v1/documents/{doc['grup']}').json()['subject_id']}"
    ).json()
    meeting = detail["meetings"][0]
    assert meeting["materials"][0]["di_bank"] is True
    assert meeting["quizzes"][0]["di_bank"] is True
    assert meeting["materials"][0]["grup_dokumen"] == doc["grup"]


# ------------------------------------------------------------------ generate AI dokumen
DOKUMEN_AI = MATERI + "\n" + PG + "\n" + ESAI


def _fake_ai(monkeypatch, responses):
    queue = list(responses)

    def _fake(setting, messages, temperature=0.7):
        assert queue, "fake AI kehabisan jawaban"
        return queue.pop(0)

    monkeypatch.setattr("app.routers.generate.chat_completion", _fake)


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
    lengkap = next(p for p in packs if p["nama"] == "Kelas Lengkap")
    return lengkap["id"]


def test_generate_dokumen_terpadu_dan_terbit(client, monkeypatch):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _setting_ai(client, csrf)
    _, mid = setup_kelas(client, csrf)
    pack_id = _paket_lengkap(client)
    _fake_ai(monkeypatch, ["```tcml\n" + DOKUMEN_AI + "\n```"])

    res = client.post(
        "/api/v1/generate",
        json={
            "kind": "dokumen",
            "pack_id": pack_id,
            "brief": {"topik": "Penjumlahan", "jumlah_soal": 1},
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    drafts = res.json()["drafts"]
    # seluruh keluaran = SATU draf dokumen, bukan tiga draf terpisah
    assert len(drafts) == 1
    d = drafts[0]
    assert d["jenis"] == "dokumen" and d["is_valid"] is True, d

    res = client.post(
        f"/api/v1/generate/drafts/{d['id']}/publish",
        json={"meeting_id": mid},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    out = res.json()
    assert out["material_id"] is not None and out["quiz_id"] is not None
    doc = client.get(f"/api/v1/documents/{out['grup']}").json()
    assert doc["material"]["id"] == out["material_id"]
    assert len(doc["quizzes"]) == 2


def test_generate_dokumen_invalid_karena_tag_asing(client, monkeypatch):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    _setting_ai(client, csrf)
    pack_id = _paket_lengkap(client)
    asing = MATERI.replace("[/MATERIAL]", "[SCRATCH 1]\nblok\n[/SCRATCH]\n[/MATERIAL]")
    # paket lengkap memuat scratch — pakai paket inti saja agar SCRATCH asing
    res = client.post(
        "/api/v1/packs",
        json={"nama": "Inti Saja", "module_slugs": ["inti-materi", "kuis-pg"]},
        headers={"x-csrf-token": csrf},
    )
    pack_id = res.json()["id"]
    _fake_ai(monkeypatch, [asing + "\n" + PG])
    res = client.post(
        "/api/v1/generate",
        json={"kind": "dokumen", "pack_id": pack_id, "brief": {"topik": "X"}},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    d = res.json()["drafts"][0]
    assert d["is_valid"] is False
    assert any("SCRATCH" in e["message"] for e in d["errors"])


def test_impor_dokumen_terpadu(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    pack_id = _paket_lengkap(client)
    res = client.post(
        "/api/v1/generate/import",
        json={"kind": "dokumen", "pack_id": pack_id, "teks": DOKUMEN_AI},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    drafts = res.json()["drafts"]
    assert len(drafts) == 1 and drafts[0]["jenis"] == "dokumen"
    assert drafts[0]["is_valid"] is True
    # simpan ke bank sebagai satu dokumen bank
    res = client.post(
        f"/api/v1/generate/drafts/{drafts[0]['id']}/save-bank",
        json={},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    grup = res.json()["grup"]
    tersimpan = client.get(f"/api/v1/bank/documents/{grup}").json()
    assert tersimpan["material"] is not None and len(tersimpan["quizzes"]) == 2


# ------------------------------------------------------------------ template kelas
def test_template_kelas_mempertahankan_pasangan(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    sid, _ = setup_kelas(client, csrf)
    detail = client.get(f"/api/v1/subjects/{sid}").json()
    mid = detail["meetings"][0]["id"]
    doc = buat_dokumen(client, csrf, mid, jenis="kuis", teks_kuis_esai=None).json()

    res = client.post(
        f"/api/v1/subjects/{sid}/save-template",
        json={"nama": "Tpl Dokumen"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    tpl = res.json()
    res = client.post(
        f"/api/v1/class-templates/{tpl['id']}/instantiate",
        json={"nama": "Kelas Salinan"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    baru = client.get(f"/api/v1/subjects/{res.json()['id']}").json()
    meeting = baru["meetings"][0]
    assert len(meeting["materials"]) == 1 and len(meeting["quizzes"]) == 1
    grup_baru = meeting["materials"][0]["grup_dokumen"]
    assert grup_baru and grup_baru != doc["grup"]
    assert meeting["quizzes"][0]["grup_dokumen"] == grup_baru
    assert meeting["materials"][0]["jenis"] == "kuis"
