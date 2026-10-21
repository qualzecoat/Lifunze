"""Konversi dokumen TCML (materi/latihan/proyek) <-> model blok untuk
Mode Blok editor materi.

Model blok (JSON):
  {"jenis": "paragraf"|"judul"|..., "teks": "..."}            — blok teks
  {"jenis": "langkah"|"tugas"|"syarat"|"rubrik", "items": []} — blok daftar
  {"jenis": "tabel", "baris": [[sel, ...], ...]}               — tabel pipa
  {"jenis": "sprite", "nama": "...", "deskripsi": "..."}       — kartu sprite

Dokumen yang strukturnya tidak bisa dipetakan bersih (tag tak dikenal,
daftar yatim, judul ganda, tanpa akar, dll) ditandai bisa_formulir=False
— editor membiarkannya di Mode TCML, sama seperti filosofi editor kuis.
"""

from __future__ import annotations

from .core import ASTBuilder, BlockNode, TextNode, Tokenizer
from .engine import parse_material

TEXT_BLOCKS = {
    "TITLE": "judul",
    "HEADING": "heading",
    "PARAGRAPH": "paragraf",
    "NOTE": "catatan",
    "WARNING": "peringatan",
    "SUMMARY": "ringkasan",
    "EXAMPLE": "contoh",
    "OBJECTIVE": "tujuan",
    "DESCRIPTION": "deskripsi",
    "OUTPUT": "luaran",
    "HINT": "petunjuk",
    "EXPECTED": "harapan",
    "FORMULA": "rumus",
    "CODE": "kode",
    "BLOCKS": "blok-scratch",
}

LIST_BLOCKS = {
    "STEPS": ("langkah", "STEP"),
    "TASKS": ("tugas", "TASK"),
    "REQUIREMENTS": ("syarat", "REQUIREMENT"),
    "RUBRIC": ("rubrik", "CRITERIA"),
}

ROOTS = {"MATERIAL", "EXERCISE", "PROJECT"}


def _raw_text(node) -> str:
    text = ""
    for child in node.children:
        if isinstance(child, TextNode):
            text += child.text
        elif isinstance(child, BlockNode):
            text += _raw_text(child)
    return text


def _leaf_text(node) -> str | None:
    """Teks polos sebuah node daun; None bila ada blok bersarang di dalamnya."""
    if any(isinstance(c, BlockNode) for c in node.children):
        return None
    return _raw_text(node).strip()


def _split_tag(tag: str) -> tuple[str, str | None]:
    parts = tag.split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1].strip()
    return tag, None


def _table_rows(node) -> list[list[str]] | None:
    """Baris tabel dari node DATASET/TABLE; None bila strukturnya aneh."""
    table_node = node
    if node.tag == "DATASET":
        table_node = None
        for child in node.children:
            if isinstance(child, BlockNode) and child.tag == "TABLE":
                if table_node is not None:
                    return None
                table_node = child
            elif isinstance(child, TextNode) and child.text.strip():
                return None
        if table_node is None:
            # DATASET tanpa TABLE: pakai teks mentahnya sendiri.
            table_node = node
    raw = _raw_text(table_node).strip()
    rows = []
    for line in raw.split("\n"):
        line = line.strip()
        if line:
            rows.append([sel.strip() for sel in line.split("|")])
    return rows


def document_to_blocks(teks: str) -> dict:
    res = parse_material(teks)
    if not res["success"]:
        return {
            "success": False,
            "root": None,
            "blocks": [],
            "bisa_formulir": False,
            "alasan": None,
            "errors": res["errors"],
        }

    tokens = Tokenizer(teks).tokenize()
    ast, _ = ASTBuilder(tokens).build()

    root_node = None
    for child in ast.children:
        if isinstance(child, BlockNode):
            if root_node is not None:
                return _kompleks("Dokumen memiliki lebih dari satu akar.")
            root_node = child
        elif child.text.strip():
            return _kompleks("Ada teks di luar akar dokumen.")
    if root_node is None or root_node.tag not in ROOTS:
        return _kompleks("Dokumen tidak berakar [MATERIAL]/[EXERCISE]/[PROJECT].")

    blocks: list[dict] = []
    jumlah_judul = 0

    def gagal(alasan: str) -> dict:
        return _kompleks(alasan, root=root_node.tag)

    for child in root_node.children:
        if isinstance(child, TextNode):
            if child.text.strip():
                blocks.append({"jenis": "paragraf", "teks": child.text.strip()})
            continue
        base, arg = _split_tag(child.tag)
        if base in TEXT_BLOCKS:
            if arg:
                return gagal(f"Tag [{base}] memakai argumen yang tidak didukung Mode Blok.")
            teks_isi = _leaf_text(child)
            if teks_isi is None:
                return gagal(f"Isi [{base}] mengandung blok bersarang.")
            if base == "TITLE":
                jumlah_judul += 1
                if jumlah_judul > 1:
                    return gagal("Dokumen memiliki lebih dari satu [TITLE].")
            blocks.append({"jenis": TEXT_BLOCKS[base], "teks": teks_isi})
        elif base in LIST_BLOCKS:
            jenis, item_tag = LIST_BLOCKS[base]
            items = []
            for sub in child.children:
                if isinstance(sub, TextNode):
                    if sub.text.strip():
                        return gagal(f"[{base}] berisi teks di luar [{item_tag}].")
                    continue
                if sub.tag != item_tag:
                    return gagal(f"[{base}] berisi tag selain [{item_tag}].")
                isi = _leaf_text(sub)
                if isi is None:
                    return gagal(f"Isi [{item_tag}] mengandung blok bersarang.")
                items.append(isi)
            blocks.append({"jenis": jenis, "items": items})
        elif base in ("DATASET", "TABLE"):
            rows = _table_rows(child)
            if rows is None:
                return gagal("Struktur tabel tidak bisa dipetakan ke Mode Blok.")
            blocks.append({"jenis": "tabel", "baris": rows})
        elif base == "SCRATCH":
            isi = _leaf_text(child)
            if isi is None:
                return gagal("Isi [SCRATCH] tidak bisa dipetakan.")
            blocks.append({"jenis": "scratch", "teks": isi or (arg or "")})
        elif base == "SPRITE":
            raw = _leaf_text(child)
            if raw is None:
                return gagal("Isi [SPRITE] mengandung blok bersarang.")
            lines = [l for l in (l.strip() for l in raw.split("\n")) if l]
            blocks.append(
                {
                    "jenis": "sprite",
                    "nama": lines[0] if lines else "",
                    "deskripsi": "\n".join(lines[1:]),
                }
            )
        elif base == "CEK":
            from .cek import parse_cek_node

            parsed = parse_cek_node(child, [])
            if parsed is None:
                return gagal("Blok [CEK] tidak bisa dipetakan ke Mode Blok.")
            if parsed["tipe"] == "pilihan_ganda":
                blocks.append(
                    {
                        "jenis": "cek-pg",
                        "pertanyaan": parsed["pertanyaan"],
                        "opsi": [
                            {"teks": o["teks"], "benar": o["is_correct"]}
                            for o in parsed["options"]
                        ],
                        "bobot": parsed["bobot"],
                    }
                )
            else:
                blocks.append(
                    {
                        "jenis": "cek-esai",
                        "pertanyaan": parsed["pertanyaan"],
                        "referensi": parsed["jawaban_referensi"] or "",
                        "bobot": parsed["bobot"],
                    }
                )
        else:
            return gagal(f"Tag [{base}] belum didukung Mode Blok.")

    return {
        "success": True,
        "root": root_node.tag,
        "blocks": blocks,
        "bisa_formulir": True,
        "alasan": None,
        "errors": [],
    }


def _kompleks(alasan: str, root: str | None = None) -> dict:
    return {
        "success": True,
        "root": root,
        "blocks": [],
        "bisa_formulir": False,
        "alasan": alasan,
        "errors": [],
    }
