"""Pemecah dokumen terpadu: satu teks berisi akar materi + akar kuis.

Dokumen Lifunze boleh memuat paling banyak satu akar materi
([MATERIAL]/[EXERCISE]/[PROJECT]), satu [QUIZ] pilihan ganda, dan satu
[QUIZ] esai. Fungsi ini memisahkannya berdasarkan rentang baris AST —
dipakai router dokumen, Generate AI jenis dokumen, dan validasi terkait.
"""

from __future__ import annotations

from .core import ASTBuilder, BlockNode, TextNode, Tokenizer

MATERIAL_ROOTS = {"MATERIAL", "EXERCISE", "PROJECT"}


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
    starts = [r.line for r in roots]
    for i, r in enumerate(roots):
        end = (starts[i + 1] - 1) if i + 1 < len(roots) else len(lines)
        seg_lines = lines[r.line - 1 : end]
        close = f"[/{r.tag}]"
        last_close = None
        for j in range(len(seg_lines) - 1, -1, -1):
            if seg_lines[j].strip() == close:
                last_close = j
                break
        if last_close is None:
            errors.append({"line": r.line, "message": f"Akar [{r.tag}] tidak tertutup."})
            continue
        seg = "\n".join(seg_lines[: last_close + 1]).strip()
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
