"""Test endpoint /api/v1/parse/structure — fondasi Mode Blok editor materi."""

MATERI = """[MATERIAL]
[TITLE]Pecahan Dasar[/TITLE]
[HEADING]Pengantar[/HEADING]
[PARAGRAPH]
Halo, ini paragraf pembuka.
[/PARAGRAPH]
Teks lepas jadi paragraf.
[NOTE]Catatan penting.[/NOTE]
[STEPS]
[STEP]Langkah satu[/STEP]
[STEP]Langkah dua[/STEP]
[/STEPS]
[DATASET]
[TABLE]
Buah | Warna
Apel | Merah
[/TABLE]
[/DATASET]
[FORMULA]
a^2 + b^2 = c^2
[/FORMULA]
[/MATERIAL]"""

LATIHAN = """[EXERCISE]
[TITLE]Latihan Pecahan[/TITLE]
[TASKS]
[TASK]Kerjakan nomor 1.[/TASK]
[TASK]Kerjakan nomor 2.[/TASK]
[/TASKS]
[HINT]Ingat penyebutnya.[/HINT]
[EXPECTED]Jawaban dalam bentuk paling sederhana.[/EXPECTED]
[/EXERCISE]"""

PROYEK = """[PROJECT]
[TITLE]Proyek Scratch[/TITLE]
[DESCRIPTION]Buat game sederhana.[/DESCRIPTION]
[REQUIREMENTS]
[REQUIREMENT]Minimal 2 sprite[/REQUIREMENT]
[/REQUIREMENTS]
[OUTPUT]File .sb3[/OUTPUT]
[RUBRIC]
[CRITERIA]Kreativitas — 50[/CRITERIA]
[/RUBRIC]
[SCRATCH]104[/SCRATCH]
[SPRITE]
Kucing
Sprite utama.
[/SPRITE]
[/PROJECT]"""


def test_struktur_materi(client):
    r = client.post("/api/v1/parse/structure", json={"teks": MATERI})
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is True and d["bisa_formulir"] is True
    assert d["root"] == "MATERIAL"
    jenis = [b["jenis"] for b in d["blocks"]]
    assert jenis == [
        "judul", "heading", "paragraf", "paragraf", "catatan",
        "langkah", "tabel", "rumus",
    ]
    assert d["blocks"][0]["teks"] == "Pecahan Dasar"
    assert d["blocks"][3]["teks"] == "Teks lepas jadi paragraf."
    assert d["blocks"][5]["items"] == ["Langkah satu", "Langkah dua"]
    assert d["blocks"][6]["baris"] == [["Buah", "Warna"], ["Apel", "Merah"]]


def test_struktur_latihan(client):
    d = client.post("/api/v1/parse/structure", json={"teks": LATIHAN}).json()
    assert d["bisa_formulir"] is True and d["root"] == "EXERCISE"
    assert [b["jenis"] for b in d["blocks"]] == ["judul", "tugas", "petunjuk", "harapan"]
    assert d["blocks"][1]["items"] == ["Kerjakan nomor 1.", "Kerjakan nomor 2."]


def test_struktur_proyek_dan_scratch(client):
    d = client.post("/api/v1/parse/structure", json={"teks": PROYEK}).json()
    assert d["bisa_formulir"] is True and d["root"] == "PROJECT"
    assert [b["jenis"] for b in d["blocks"]] == [
        "judul", "deskripsi", "syarat", "luaran", "rubrik", "scratch", "sprite",
    ]
    assert d["blocks"][5]["teks"] == "104"
    assert d["blocks"][6]["nama"] == "Kucing"
    assert d["blocks"][6]["deskripsi"] == "Sprite utama."


def test_struktur_tanpa_akar_kompleks(client):
    d = client.post("/api/v1/parse/structure", json={"teks": "Halo dunia biasa."}).json()
    assert d["success"] is True
    assert d["bisa_formulir"] is False
    assert d["alasan"]


def test_struktur_judul_ganda_kompleks(client):
    teks = "[MATERIAL]\n[TITLE]Satu[/TITLE]\n[TITLE]Dua[/TITLE]\n[/MATERIAL]"
    d = client.post("/api/v1/parse/structure", json={"teks": teks}).json()
    assert d["success"] is True
    assert d["bisa_formulir"] is False


def test_struktur_blok_bersarang_kompleks(client):
    teks = "[MATERIAL]\n[TITLE]X[/TITLE]\n[PARAGRAPH]\n[NOTE]di dalam[/NOTE]\n[/PARAGRAPH]\n[/MATERIAL]"
    d = client.post("/api/v1/parse/structure", json={"teks": teks}).json()
    assert d["bisa_formulir"] is False


def test_struktur_dokumen_rusak(client):
    teks = "[MATERIAL]\n[TITLE]X[/MATERIAL]"
    d = client.post("/api/v1/parse/structure", json={"teks": teks}).json()
    assert d["success"] is False
    assert d["errors"]


MATERI_SCRATCH = """[MATERIAL]
[TITLE]Belajar Scratch[/TITLE]
Coba proyek contoh berikut — tekan bendera hijau untuk menjalankannya.
[SCRATCH]104[/SCRATCH]
[SPRITE]
Kucing
Sprite utama pada proyek contoh.
[/SPRITE]
[BLOCKS]
when green flag clicked
move (10) steps
[/BLOCKS]
[NOTE]Ganti angka pada blok move untuk mengubah jarak langkah.[/NOTE]
[/MATERIAL]"""


def test_struktur_template_scratch_editor(client):
    """Template bawaan editor (Materi Scratch) wajib bisa dibuka di Mode Blok."""
    d = client.post("/api/v1/parse/structure", json={"teks": MATERI_SCRATCH}).json()
    assert d["bisa_formulir"] is True
    assert [b["jenis"] for b in d["blocks"]] == [
        "judul", "paragraf", "scratch", "sprite", "blok-scratch", "catatan",
    ]
    assert d["blocks"][4]["teks"] == "when green flag clicked\nmove (10) steps"
