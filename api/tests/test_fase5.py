"""Test Fase 5: paket parser (CRUD/share/fork/ekspor) & generate AI (mock)."""

import pytest
from conftest import login, make_user
from fastapi.testclient import TestClient

from app.main import app

MATERI_OK = """[MATERIAL]
[TITLE]Sistem Tata Surya[/TITLE]
[PARAGRAPH]Matahari adalah bintang di pusat tata surya.[/PARAGRAPH]
[/MATERIAL]"""

MATERI_TAG_ASING = """[MATERIAL]
[TITLE]Data Kelas[/TITLE]
[TABLE]
Nama,Nilai
Andi,90
[/TABLE]
[/MATERIAL]"""

KUIS_PG_OK = """[QUIZ]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]Planet terdekat dari Matahari?[/QUESTION]
[OPTIONS]
A. Venus
B. Merkurius
[/OPTIONS]
[ANSWER]B[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""


def buat_setting(client, csrf):
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
    return res.json()["id"]


def buat_paket(client, csrf, slugs=("inti-materi",), nama="Paket Uji"):
    res = client.post(
        "/api/v1/packs",
        json={"nama": nama, "deskripsi": "untuk test", "module_slugs": list(slugs)},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    return res.json()


def fake_ai(monkeypatch, responses, capture=None):
    """Ganti chat_completion dengan jawaban antrean; capture untuk cek prompt."""
    queue = list(responses)

    def _fake(setting, messages, temperature=0.7):
        if capture is not None:
            capture.append(messages)
        assert queue, "fake AI kehabisan jawaban antrean"
        return queue.pop(0)

    monkeypatch.setattr("app.routers.generate.chat_completion", _fake)


# ---------------------------------------------------------------- paket CRUD
def test_modul_dan_paket_crud(client):
    make_user("guru1", "guru")
    make_user("guru2", "guru")
    csrf = login(client, "guru1")
    modules = client.get("/api/v1/packs/modules").json()
    assert len(modules) == 9  # + modul cek-pemahaman
    pg = next(m for m in modules if m["slug"] == "kuis-pg")
    assert "WEIGHT" in pg["tags"] and pg["examples"]

    pack = buat_paket(client, csrf, slugs=("inti-materi", "kuis-pg"))
    assert set(pack["allowed_roots"]) == {"MATERIAL", "EXERCISE", "PROJECT", "QUIZ"}

    c2 = TestClient(app)
    login(c2, "guru2")
    assert c2.get(f"/api/v1/packs/{pack['id']}").status_code == 404

    res = client.patch(
        f"/api/v1/packs/{pack['id']}",
        json={"nama": "Paket Baru", "deskripsi": None, "module_slugs": ["kuis-esai"]},
        headers={"x-csrf-token": csrf},
    )
    assert res.json()["allowed_roots"] == ["QUIZ"]
    assert res.json()["modules"][0]["slug"] == "kuis-esai"


def test_share_dan_fork(client):
    g1 = make_user("guru1", "guru")
    g2 = make_user("guru2", "guru")
    make_user("guru3", "guru")
    csrf1 = login(client, "guru1")
    pack = buat_paket(client, csrf1)

    c2 = TestClient(app)
    csrf2 = login(c2, "guru2")
    c3 = TestClient(app)
    login(c3, "guru3")

    # bagikan ke guru2 saja
    res = client.put(
        f"/api/v1/packs/{pack['id']}/share",
        json={"mode": "users", "user_ids": [g2]},
        headers={"x-csrf-token": csrf1},
    )
    assert res.json()["shared_with_ids"] == [g2]
    assert c2.get(f"/api/v1/packs/{pack['id']}").status_code == 200
    assert len(c2.get("/api/v1/packs/shared").json()) == 1
    assert c3.get(f"/api/v1/packs/{pack['id']}").status_code == 404

    # fork oleh guru2 -> salinan miliknya, privat
    res = c2.post(f"/api/v1/packs/{pack['id']}/fork", headers={"x-csrf-token": csrf2})
    assert res.status_code == 201
    fork = res.json()
    assert fork["punya_saya"] is True and fork["visibilitas"] == "private"
    assert fork["nama"].endswith("(Fork)")

    # bagikan ke semua -> guru3 bisa; lalu cabut -> guru2 kehilangan akses paket asli
    client.put(
        f"/api/v1/packs/{pack['id']}/share",
        json={"mode": "all"},
        headers={"x-csrf-token": csrf1},
    )
    assert c3.get(f"/api/v1/packs/{pack['id']}").status_code == 200
    client.put(
        f"/api/v1/packs/{pack['id']}/share",
        json={"mode": "private"},
        headers={"x-csrf-token": csrf1},
    )
    assert c2.get(f"/api/v1/packs/{pack['id']}").status_code == 404
    # fork guru2 tetap miliknya
    assert c2.get(f"/api/v1/packs/{fork['id']}").status_code == 200


def test_ekspor_paket_markdown(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    pack = buat_paket(client, csrf, slugs=("kuis-pg",))
    res = client.get(f"/api/v1/packs/{pack['id']}/export")
    assert res.status_code == 200
    assert "text/markdown" in res.headers["content-type"]
    assert "# Paket Parser TCML" in res.text
    assert "[WEIGHT]" in res.text  # spec modul kuis-pg ikut
    assert "Kuis Pilihan Ganda" in res.text


def test_paket_bawaan_otomatis(client):
    make_user("guru1", "guru")
    login(client, "guru1")
    packs = client.get("/api/v1/packs").json()
    names = {p["nama"] for p in packs}
    assert {"Mapel Umum", "Kuis Pilihan Ganda", "Kuis Esai", "Kelas Lengkap"} <= names
    # idempoten: panggil lagi tidak menggandakan
    assert len(client.get("/api/v1/packs").json()) == len(packs)


# ------------------------------------------------------------------ generate
def test_generate_bundle_validasi_dua_lapis(client, monkeypatch):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    buat_setting(client, csrf)
    pack = buat_paket(client, csrf, slugs=("inti-materi",))
    bundle = "```tcml\n" + MATERI_OK + "\n" + MATERI_TAG_ASING + "\n```"
    capture = []
    fake_ai(monkeypatch, [bundle], capture=capture)

    res = client.post(
        "/api/v1/generate",
        json={"kind": "materi", "pack_id": pack["id"], "brief": {"topik": "Tata surya"}},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    drafts = res.json()["drafts"]
    assert len(drafts) == 2
    ok_draft = next(d for d in drafts if d["judul"] == "Sistem Tata Surya")
    bad_draft = next(d for d in drafts if d["judul"] == "Data Kelas")
    assert ok_draft["is_valid"] is True
    assert bad_draft["is_valid"] is False
    assert any("[TABLE]" in e["message"] for e in bad_draft["errors"])

    # klaim hemat konteks: prompt sistem HANYA memuat modul terpilih
    system_prompt = capture[0][0]["content"]
    assert "Inti Materi" in system_prompt
    assert "Tabel & Dataset" not in system_prompt

    # draf valid bisa disimpan ke bank; yang invalid ditolak
    res = client.post(
        f"/api/v1/generate/drafts/{ok_draft['id']}/save-bank",
        json={},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    assert len(client.get("/api/v1/bank/materials").json()) == 1
    res = client.post(
        f"/api/v1/generate/drafts/{bad_draft['id']}/save-bank",
        json={},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400


def test_generate_kuis_dan_publish(client, monkeypatch):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    buat_setting(client, csrf)
    pack = buat_paket(client, csrf, slugs=("kuis-pg",))
    fake_ai(monkeypatch, [KUIS_PG_OK])

    sid = client.post("/api/v1/subjects", json={"nama": "IPA"}, headers={"x-csrf-token": csrf}).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf}).json()["id"]

    res = client.post(
        "/api/v1/generate",
        json={"kind": "kuis_pg", "pack_id": pack["id"], "brief": {"topik": "Tata surya", "jumlah_soal": 1}},
        headers={"x-csrf-token": csrf},
    )
    draft = res.json()["drafts"][0]
    assert draft["jenis"] == "quiz" and draft["tipe_quiz"] == "pilihan_ganda"
    assert draft["is_valid"] is True

    res = client.post(
        f"/api/v1/generate/drafts/{draft['id']}/publish",
        json={"meeting_id": mid, "judul": "Kuis Tata Surya"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    quiz_id = res.json()["quiz_id"]
    detail = client.get(f"/api/v1/quizzes/{quiz_id}").json()
    assert len(detail["questions"]) == 1


def test_generate_tanpa_setting_dan_milik_orang(client, monkeypatch):
    make_user("guru1", "guru")
    make_user("guru2", "guru")
    csrf = login(client, "guru1")
    pack = buat_paket(client, csrf, slugs=("kuis-pg",))
    fake_ai(monkeypatch, [KUIS_PG_OK])
    # belum punya pengaturan AI -> 400
    res = client.post(
        "/api/v1/generate",
        json={"kind": "kuis_pg", "pack_id": pack["id"], "brief": {"topik": "X"}},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400
    # setting milik guru2 tidak bisa dipakai guru1
    c2 = TestClient(app)
    csrf2 = login(c2, "guru2")
    sid2 = buat_setting(c2, csrf2)
    buat_setting(client, csrf)
    res = client.post(
        "/api/v1/generate",
        json={"kind": "kuis_pg", "pack_id": pack["id"], "ai_setting_id": sid2, "brief": {"topik": "X"}},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 404


def test_repair_draf_dan_batasnya(client, monkeypatch):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    buat_setting(client, csrf)
    pack = buat_paket(client, csrf, slugs=("inti-materi",))
    # generate -> draf invalid (tag TABLE di luar paket)
    fake_ai(monkeypatch, [MATERI_TAG_ASING, MATERI_TAG_ASING, MATERI_OK])
    res = client.post(
        "/api/v1/generate",
        json={"kind": "materi", "pack_id": pack["id"], "brief": {"topik": "Data"}},
        headers={"x-csrf-token": csrf},
    )
    draft = res.json()["drafts"][0]
    assert draft["is_valid"] is False

    # repair 1: masih invalid; repair 2: valid
    res = client.post(f"/api/v1/generate/drafts/{draft['id']}/repair", headers={"x-csrf-token": csrf})
    assert res.json()["is_valid"] is False
    res = client.post(f"/api/v1/generate/drafts/{draft['id']}/repair", headers={"x-csrf-token": csrf})
    assert res.json()["is_valid"] is True
    assert res.json()["judul"] == "Sistem Tata Surya"
    # sudah valid -> repair ditolak
    res = client.post(f"/api/v1/generate/drafts/{draft['id']}/repair", headers={"x-csrf-token": csrf})
    assert res.status_code == 400


def test_repair_melebihi_batas(client, monkeypatch):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    buat_setting(client, csrf)
    pack = buat_paket(client, csrf, slugs=("inti-materi",))
    fake_ai(monkeypatch, [MATERI_TAG_ASING, MATERI_TAG_ASING, MATERI_TAG_ASING])
    res = client.post(
        "/api/v1/generate",
        json={"kind": "materi", "pack_id": pack["id"], "brief": {"topik": "Data"}},
        headers={"x-csrf-token": csrf},
    )
    draft_id = res.json()["drafts"][0]["id"]
    client.post(f"/api/v1/generate/drafts/{draft_id}/repair", headers={"x-csrf-token": csrf})
    client.post(f"/api/v1/generate/drafts/{draft_id}/repair", headers={"x-csrf-token": csrf})
    res = client.post(f"/api/v1/generate/drafts/{draft_id}/repair", headers={"x-csrf-token": csrf})
    assert res.status_code == 400
    assert "Batas perbaikan" in res.json()["detail"]


def test_impor_konten_eksternal(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")
    pack = buat_paket(client, csrf, slugs=("inti-materi",))
    bundle = MATERI_OK + "\n" + MATERI_TAG_ASING
    res = client.post(
        "/api/v1/generate/import",
        json={"kind": "materi", "pack_id": pack["id"], "teks": bundle},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    drafts = res.json()["drafts"]
    assert len(drafts) == 2
    assert sum(1 for d in drafts if d["is_valid"]) == 1
    # teks tanpa root block -> 400
    res = client.post(
        "/api/v1/generate/import",
        json={"kind": "materi", "pack_id": pack["id"], "teks": "halo ini bukan tcml"},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400
