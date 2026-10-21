"""Pemecah dokumen terpadu: satu teks berisi akar materi + akar kuis.

Dokumen Lifunze boleh memuat paling banyak satu akar materi
([MATERIAL]/[EXERCISE]/[PROJECT]), satu [QUIZ] pilihan ganda, dan satu
[QUIZ] esai. Fungsi ini memisahkannya berdasarkan rentang baris AST —
dipakai router dokumen, Generate AI jenis dokumen, dan validasi terkait.
"""

from __future__ import annotations

from .core import ASTBuilder, BlockNode, TextNode, Tokenizer

MATERIAL_ROOTS = {"MATERIAL", "EXERCISE", "PROJECT"}


def _rentang_akar(teks: str) -> list[tuple[int, int, int]]:
    """Rentang tiap akar dokumen dari TOKEN: [(baris_mulai, baris_tutup,
    kolom_akhir)] — kolom_akhir = posisi tepat sesudah tag penutup pada
    baris tutup. Audit #16: dulu segmen dicari dengan asumsi tag penutup
    sendirian sebaris; penutup yang sebaris dengan teks lain membuat akar
    ditolak ("tidak tertutup") atau hilang diam-diam."""
    tokens = Tokenizer(teks).tokenize()
    lines = teks.split("\n")
    stack: list = []
    rentang: list[tuple[int, int, int]] = []
    for t in tokens:
        if t.type == "OPEN_TAG":
            stack.append(t)
        elif t.type == "CLOSE_TAG" and stack and stack[-1].value == t.value:
            buka = stack.pop()
            if not stack:
                baris = lines[t.line - 1] if 0 < t.line <= len(lines) else ""
                idx = baris.find(f"[/{t.value}]")
                rentang.append((buka.line, t.line, (idx + len(t.value) + 3) if idx >= 0 else len(baris)))
    return rentang


def split_document(teks: str) -> dict:
    """-> {"materi": str|None, "kuis_pg": str|None, "kuis_esai": str|None,
    "errors": [{line, message}]}"""
    from .quiz import parse_quiz_v2

    tokens = Tokenizer(teks).tokenize()
    ast, build_errors = ASTBuilder(tokens).build()
    lines = teks.split("\n")
    parts: dict = {"materi": None, "kuis_pg": None, "kuis_esai": None}
    errors: list[dict] = [dict(e) for e in build_errors]

    for child in ast.children:
        if isinstance(child, TextNode) and child.text.strip():
            errors.append(
                {"line": child.line, "message": "Ada teks di luar akar dokumen."}
            )
            break

    roots = [c for c in ast.children if isinstance(c, BlockNode)]
    rentang = _rentang_akar(teks)
    for i, r in enumerate(roots):
        if i < len(rentang) and rentang[i][0] == r.line:
            mulai, tutup, kolom = rentang[i]
            seg_lines = lines[mulai - 1 : tutup - 1]
            seg_lines.append(lines[tutup - 1][:kolom])
            seg = "\n".join(seg_lines).strip()
        else:
            errors.append({"line": r.line, "message": f"Akar [{r.tag}] tidak tertutup."})
            continue
        if r.tag in MATERIAL_ROOTS:
            if parts["materi"] is not None:
                errors.append(
                    {"line": r.line, "message": "Dokumen memiliki lebih dari satu bagian materi."}
                )
            else:
                parts["materi"] = seg
        elif r.tag == "QUIZ":
            res = parse_quiz_v2(seg)
            if not res["success"]:
                errors.extend(dict(e) for e in res["errors"])
                continue
            tipe = (res["content"] or {}).get("tipe")
            key = "kuis_esai" if tipe == "teks" else "kuis_pg"
            if parts[key] is not None:
                errors.append(
                    {
                        "line": r.line,
                        "message": "Dokumen memiliki dua kuis " + ("esai." if key == "kuis_esai" else "pilihan ganda."),
                    }
                )
            else:
                parts[key] = seg
        else:
            errors.append(
                {"line": r.line, "message": f"Akar [{r.tag}] tidak dikenal untuk dokumen terpadu."}
            )
    return {**parts, "errors": errors}
