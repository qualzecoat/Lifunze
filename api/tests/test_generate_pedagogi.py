"""Tes Batch 3 (2026-10-21): generate memakai template pedagogi —
spec tersaring, instruksi urutan, DUA TAHAP (materi dulu, soal sisipan
ditulis dari materi jadi lalu disisipkan per bagian), kepadatan mengganti
kuota untuk materi, dan cek struktur lunak."""

from tests.conftest import login, make_user

MATERI_2_BAGIAN = """[MATERIAL]
[TITLE]Pecahan[/TITLE]
[HEADING]Pengertian Pecahan[/HEADING]
[PARAGRAPH]Pecahan adalah bagian dari keseluruhan yang dibagi sama besar.[/PARAGRAPH]
[EXAMPLE]Setengah pizza berarti 1 dari 2 potong yang sama besar.[/EXAMPLE]
[HEADING]Menyederhanakan Pecahan[/HEADING]
[PARAGRAPH]Bagi pembilang dan penyebut dengan FPB-nya.[/PARAGRAPH]
[SUMMARY]Pecahan menyatakan bagian dari keseluruhan dan bisa disederhanakan.[/SUMMARY]
[/MATERIAL]"""

UNIT_CEK = """[TARGET]Pengertian Pecahan[/TARGET]
[CEK]
[QUESTION]Apa arti pecahan 1/2?[/QUESTION]
[OPTIONS]
A. Satu dari dua bagian sama besar
B. Dua dari satu bagian utuh
[/OPTIONS]
[ANSWER]A[/ANSWER]
[/CEK]
[TARGET]Menyederhanakan Pecahan[/TARGET]
[CEK]
[TYPE]essay[/TYPE]
[QUESTION]Jelaskan cara menyederhanakan pecahan 4/8.[/QUESTION]
[ANSWER]Bagi pembilang dan penyebut dengan FPB 4 sehingga menjadi 1/2.[/ANSWER]
[/CEK]"""

KUIS_PG = """[QUIZ]
[TITLE]Kuis[/TITLE]
[TYPE]pilihan_ganda[/TYPE]
[QUESTION 1]
[QUESTION]Ibu kota Indonesia?[/QUESTION]
[OPTIONS]
A. Jakarta
B. Bandung
[/OPTIONS]
[ANSWER]A[/ANSWER]
[/QUESTION 1]
[/QUIZ]"""


def buat_setting(client, csrf):
    res = client.post(
        "/api/v1/ai/settings",
        json={"nama": "Tes", "base_url": "https://api.contoh.com/v1",
              "api_key": "sk-tes-123456", "model": "model-tes", "is_default": True},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def buat_paket_lengkap(client, csrf):
    res = client.post(
        "/api/v1/packs",
        json={"nama": "Paket Uji Lengkap", "module_slugs": [
            "inti-materi", "tabel-data", "formula-kode", "latihan",
            "proyek", "cek-pemahaman", "kuis-pg", "kuis-esai",
        ]},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    return res.json()


def fake_ai(monkeypatch, responses, capture=None):
    queue = list(responses)

    def _fake(setting, messages, temperature=0.7):
        if capture is not None:
            capture.append(messages)
        assert queue, "fake AI kehabisan jawaban"
        return queue.pop(0)

    monkeypatch.setattr("app.routers.generate.chat_completion", _fake)


def _preset_id(client, nama="Konsep Bertahap"):
    data = client.get("/api/v1/templates").json()
    return next(t["id"] for t in data["preset"] if t["nama"] == nama)


def test_generate_dua_tahap_dengan_template(client, monkeypatch):
    make_user("guru_gen", "guru")
    csrf = login(client, "guru_gen")
    buat_setting(client, csrf)
    pack = buat_paket_lengkap(client, csrf)
    capture = []
    fake_ai(monkeypatch, [MATERI_2_BAGIAN, UNIT_CEK], capture=capture)

    res = client.post(
        "/api/v1/generate",
        json={
            "kind": "dokumen",
            "pack_id": pack["id"],
            "template_id": _preset_id(client),
            "brief": {
                "topik": "Pecahan", "jenis_dokumen": "materi",
                "kepadatan_cek": "sedang", "jumlah_soal": 10,
            },
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["dua_tahap"] is True
    assert len(capture) == 2, "harus dua panggilan AI"

    prompt1 = capture[0][1]["content"]
    assert "Jumlah soal: 10" not in prompt1, "kuota tidak boleh bocor untuk materi berkepadatan"
    assert "CATATAN TAHAP PENULISAN" in prompt1
    assert "ALUR MENGAJAR" in prompt1
    prompt2 = capture[1][1]["content"]
    assert "Tulis 4 soal sisipan" in prompt2  # kepadatan sedang = 4

    draft = body["drafts"][0]
    assert draft["is_valid"], draft["errors"]
    teks = draft["teks_mentah"]
    assert teks.count("[CEK]") == 2
    # CEK pertama menempel di bagian pertama (sebelum heading kedua).
    assert teks.index("[CEK]") < teks.index("[HEADING]Menyederhanakan")
    assert body["peringatan_struktur"] == []


def test_generate_tanpa_template_tetap_satu_tahap(client, monkeypatch):
    make_user("guru_legacy", "guru")
    csrf = login(client, "guru_legacy")
    buat_setting(client, csrf)
    pack = buat_paket_lengkap(client, csrf)
    capture = []
    fake_ai(monkeypatch, [KUIS_PG], capture=capture)
    res = client.post(
        "/api/v1/generate",
        json={"kind": "kuis_pg", "pack_id": pack["id"],
              "brief": {"topik": "Geografi", "jumlah_soal": 3}},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    assert res.json()["dua_tahap"] is False
    assert len(capture) == 1
    assert "Jumlah soal: 3" in capture[0][1]["content"]


def test_sisipkan_cek_dan_cek_struktur_unit():
    from app.models import PedagogyTemplate
    from app.routers.generate import _cek_struktur, _sisipkan_cek

    blok = ("[CEK]\n[QUESTION]Q?[/QUESTION]\n[OPTIONS]\nA. x\nB. y\n[/OPTIONS]\n"
            "[ANSWER]A[/ANSWER]\n[/CEK]")
    # Target tidak dikenal -> jatuh ke bagian terpanjang.
    out = _sisipkan_cek(MATERI_2_BAGIAN, [("Heading Ngawur", blok)], 4)
    assert out.count("[CEK]") == 1
    assert out.index("[CEK]") > out.index("[HEADING]Pengertian")

    t = PedagogyTemplate(nama="Uji", bagian=[
        {"peran": "ringkasan", "label": "Penutup", "status": "wajib", "modul": [], "catatan": ""},
        {"peran": "cek", "label": "Cek", "status": "opsional", "modul": [], "catatan": ""},
    ])
    assert _cek_struktur(t, MATERI_2_BAGIAN) == []  # SUMMARY ada
    tanpa = MATERI_2_BAGIAN.replace("[SUMMARY]Pecahan menyatakan bagian dari keseluruhan dan bisa disederhanakan.[/SUMMARY]\n", "")
    peringatan = _cek_struktur(t, tanpa)
    assert len(peringatan) == 1 and "Penutup" in peringatan[0]
