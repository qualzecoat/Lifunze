# Registry modul tag TCML.
#
# Engine inti (core.py) tidak tahu tag spesifik; renderer (renderers.py)
# mengimplementasikan tag-tag di bawah ini. Registry ini adalah metadata
# pengelompokan tag per MODUL — fondasi sistem Paket Parser (Fase 5):
# sebuah paket adalah komposisi modul-modul dari daftar ini, dan hanya
# spesifikasi modul terpilih yang nanti dikirim ke AI.
#
# Menambah tag baru = tambah renderer di renderers.py + daftarkan di sini.

MODULES = {
    "inti-materi": {
        "nama": "Inti Materi",
        "roots": ["MATERIAL", "EXERCISE", "PROJECT"],
        "tags": [
            "TITLE", "HEADING", "PARAGRAPH", "NOTE", "WARNING", "SUMMARY",
            "EXAMPLE", "OBJECTIVE", "STEPS", "STEP",
        ],
    },
    "tabel-data": {
        "nama": "Tabel & Dataset",
        "roots": [],
        "tags": ["DATASET", "TABLE"],
    },
    "formula-kode": {
        "nama": "Formula & Kode",
        "roots": [],
        "tags": ["FORMULA", "CODE"],
    },
    "latihan": {
        "nama": "Latihan & Tugas Praktik",
        "roots": ["EXERCISE"],
        "tags": ["TASKS", "TASK", "HINT", "EXPECTED"],
    },
    "proyek": {
        "nama": "Proyek",
        "roots": ["PROJECT"],
        "tags": [
            "DESCRIPTION", "REQUIREMENTS", "REQUIREMENT", "OUTPUT",
            "RUBRIC", "CRITERIA",
        ],
    },
    "kuis-pg": {
        "nama": "Kuis Pilihan Ganda",
        "roots": ["QUIZ"],
        "tags": ["TYPE", "QUESTION_BLOCK", "QUESTION", "OPTIONS", "ANSWER", "WEIGHT"],
    },
    "kuis-esai": {
        "nama": "Kuis Esai",
        "roots": ["QUIZ"],
        "tags": ["TYPE", "QUESTION_BLOCK", "QUESTION", "ANSWER", "WEIGHT"],
    },
    # "scratch": modul khusus Scratch — direncanakan Fase 7 (belum ada renderer).
}

ROOT_BLOCKS = ["MATERIAL", "EXERCISE", "PROJECT", "QUIZ"]

TAG_TO_MODULE = {}
for _slug, _mod in MODULES.items():
    for _tag in _mod["tags"]:
        TAG_TO_MODULE.setdefault(_tag, []).append(_slug)
