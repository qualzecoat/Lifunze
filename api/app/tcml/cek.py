"""Soal sisipan [CEK] — "Cek Pemahaman" di dalam materi.

Berbeda dari [QUIZ] (kuis betulan: ada halaman mulai, jendela, timer, dan
attempt), blok [CEK] adalah soal LATIHAN ringan yang hidup DI DALAM dokumen
materi/latihan/proyek, tepat di antara blok bacaan:

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
    [QUESTION]Jelaskan mengapa menyimpan berkala itu penting.[/QUESTION]
    [ANSWER]Agar pekerjaan tidak hilang saat listrik padam atau aplikasi
    tertutup tiba-tiba.[/ANSWER]
    [/CEK]

Sifatnya (keputusan Qualze 2026-10-21):
- tanpa waktu/jendela/attempt; dikerjakan langsung di halaman materi;
- PG dinilai otomatis, boleh diulang, nilai terakhir yang dipakai dan
  masuk sebagai NILAI MATERI;
- esai bersifat cek mandiri: jawaban referensi ([ANSWER], WAJIB ada)
  hanya dibuka SETELAH siswa menjawab.

Modul ini menyediakan parse satu node [CEK] (dipakai renderer materi
untuk validasi + placeholder) dan ekstraksi semua [CEK] dari teks materi
(dipakai endpoint jawab & nilai). Kunci jawaban TIDAK PERNAH ikut ke
HTML hasil render — pengecekan selalu di server dari teks mentah.
"""

from __future__ import annotations

import re

from .core import ASTBuilder, BlockNode, TextNode, Tokenizer
from .quiz import _find_child, _parse_options, _raw_text

# Tag blok konten yang boleh hidup di dalam [QUIZ] sebagai pengantar /
# selingan antar soal (prolog, hint, catatan) — dipakai parse_quiz_v2.
KONTEN_KUIS_TAGS = {"NOTE", "HINT", "EXAMPLE", "WARNING", "SUMMARY"}

# Isi blok-blok ini bersifat TEKS MENTAH (kode, rumus, data, sprite, blok
# Scratch). [CEK] yang muncul di dalamnya adalah CONTOH literal, bukan soal
# sisipan sungguhan: tidak boleh diekstrak, divalidasi, atau diskor
# (audit #6 — dulu contoh [CEK] di dalam [CODE] menjadi "soal hantu" yang
# masuk penyebut skor tapi tidak pernah tampil, dan contoh yang tidak valid
# menggagalkan penyimpanan seluruh materi).
RAW_BLOCK_TAGS = {"CODE", "FORMULA", "BLOCKS", "DATASET", "TABLE", "SCRATCH", "SPRITE"}


def parse_cek_node(node: BlockNode, errors: list) -> dict | None:
    """Parse satu node [CEK]; kesalahan ditambahkan ke `errors`.

    Mengembalikan dict soal ternormalisasi (format server, MEMUAT kunci):
      {"tipe", "pertanyaan", "bobot", "options": [{"label","teks","is_correct"}],
       "jawaban_referensi": str | None}
    atau None bila tidak valid.
    """
    q_node = _find_child(node, "QUESTION")
    pertanyaan = _raw_text(q_node) if q_node is not None else ""
    if not pertanyaan:
        errors.append({"line": node.line, "message": "Blok [CEK] wajib punya [QUESTION] berisi pertanyaan."})
        return None

    type_node = _find_child(node, "TYPE")
    raw_type = _raw_text(type_node).lower() if type_node is not None else ""
    if raw_type in ("essay", "esai", "teks", "text"):
        tipe = "teks"
    elif raw_type in ("pilihan_ganda", "multiple_choice", "mcq", ""):
        tipe = "pilihan_ganda"
    else:
        errors.append({"line": type_node.line if type_node else node.line,
                       "message": f"Isi [TYPE] di [CEK] tidak dikenal: '{raw_type}' (pilihan_ganda / essay)."})
        return None

    bobot = 1.0
    w_node = _find_child(node, "WEIGHT")
    if w_node is not None:
        w_raw = _raw_text(w_node)
        try:
            bobot = float(w_raw.replace(",", "."))
            if bobot <= 0:
                raise ValueError
        except ValueError:
            errors.append({"line": w_node.line, "message": f"Isi [WEIGHT] di [CEK] tidak valid: '{w_raw}'."})
            return None

    answer_node = _find_child(node, "ANSWER")
    answer_raw = _raw_text(answer_node) if answer_node is not None else ""
    opt_node = _find_child(node, "OPTIONS")

    if tipe == "teks" and opt_node is not None:
        errors.append({"line": node.line,
                       "message": "[CEK] esai tidak memakai [OPTIONS]; hapus [OPTIONS] atau ubah [TYPE] menjadi pilihan_ganda."})
        return None
    if tipe == "teks" or (opt_node is None and raw_type == ""):
        # Esai: [TYPE]essay eksplisit, atau tanpa TYPE & tanpa OPTIONS
        # (pertanyaan + [ANSWER] referensi saja).
        if not answer_raw:
            errors.append({"line": node.line,
                           "message": "[CEK] esai wajib punya [ANSWER] berisi jawaban referensi untuk cek mandiri siswa."})
            return None
        return {"tipe": "teks", "pertanyaan": pertanyaan, "bobot": bobot,
                "options": [], "jawaban_referensi": answer_raw}

    options = _parse_options(_raw_text(opt_node)) if opt_node is not None else []
    if len(options) < 2:
        errors.append({"line": node.line, "message": "Blok [CEK] PG wajib punya [OPTIONS] dengan minimal 2 pilihan."})
        return None
    labels = {o["label"] for o in options}
    correct = [t.upper() for t in re.split(r"[,\s]+", answer_raw) if t.strip()]
    if not correct:
        errors.append({"line": node.line, "message": "Blok [CEK] PG wajib punya [ANSWER] berisi label jawaban benar."})
        return None
    bad = [c for c in correct if c not in labels]
    if bad:
        errors.append({"line": node.line,
                       "message": f"Label jawaban {', '.join(bad)} tidak ada di [OPTIONS] blok [CEK]."})
        return None
    for o in options:
        o["is_correct"] = o["label"] in correct
    return {"tipe": "pilihan_ganda", "pertanyaan": pertanyaan, "bobot": bobot,
            "options": options, "jawaban_referensi": None}


def cek_untuk_siswa(cek: dict, indeks: int) -> dict:
    """Bentuk aman untuk siswa: TANPA kunci & referensi."""
    return {
        "indeks": indeks,
        "tipe": cek["tipe"],
        "pertanyaan": cek["pertanyaan"],
        "bobot": cek["bobot"],
        "multi": sum(1 for o in cek["options"] if o["is_correct"]) > 1,
        "options": [{"label": o["label"], "teks": o["teks"]} for o in cek["options"]],
    }


def _kumpulkan(node, hasil: list, errors: list) -> None:
    for child in node.children:
        if isinstance(child, BlockNode):
            if child.tag == "CEK":
                parsed = parse_cek_node(child, errors)
                if parsed is not None:
                    hasil.append(parsed)
            elif child.tag in RAW_BLOCK_TAGS:
                continue  # isi mentah: [CEK] di dalamnya hanya contoh literal
            else:
                _kumpulkan(child, hasil, errors)


def extract_ceks(raw_text: str) -> tuple[list[dict], list[dict]]:
    """Semua soal [CEK] dalam teks materi, berurutan sesuai dokumen.

    Mengembalikan (daftar_cek, daftar_error). Bila teks tidak memakai
    parser AST (format legacy tanpa root), hasilnya kosong.
    """
    if "[CEK]" not in raw_text:
        return [], []
    tokens = Tokenizer(raw_text).tokenize()
    ast, build_errors = ASTBuilder(tokens).build()
    if build_errors:
        return [], build_errors
    hasil: list[dict] = []
    errors: list[dict] = []
    _kumpulkan(ast, hasil, errors)
    return hasil, errors
