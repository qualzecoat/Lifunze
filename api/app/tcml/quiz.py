"""Parser kuis TCML v2 — output soal TERNORMALISASI (Fase 3).

Berbeda dari engine v1 (parse_quiz_mcq/teks yang mengembalikan dict kolom
opsi_a..e warisan), fungsi ini mengembalikan struktur yang cocok dengan
model data v2 (questions + question_options):

    {
      "tipe": "pilihan_ganda" | "teks",
      "questions": [
        {
          "tipe": "pilihan_ganda" | "teks",
          "pertanyaan": str,
          "bobot": float,                      # dari [WEIGHT] (default 1)
          "options": [{"label": "A", "teks": str, "is_correct": bool}],
          "jawaban_referensi": str | None,     # untuk esai: isi [ANSWER]
        }
      ]
    }

Ekstensi TCML v2 di dalam blok [QUESTION n]:
- [WEIGHT]2.5[/WEIGHT]            bobot soal (default 1)
- [ANSWER]B, D[/ANSWER]           PG boleh multi-jawaban-benar.
                                  Benar hanya bila himpunan pilihan siswa
                                  PERSIS sama dengan himpunan kunci.

Format legacy v1 (SOAL n / JUDUL: dsb.) tetap didukung lewat fallback ke
parser lama lalu dinormalisasi.
"""

import re

from .core import ASTBuilder, BlockNode, TextNode, Tokenizer
from .engine import parse_quiz_mcq, parse_quiz_text


def _raw_text(node) -> str:
    parts = []
    for child in node.children:
        if isinstance(child, TextNode):
            parts.append(child.text)
        elif isinstance(child, BlockNode):
            parts.append(_raw_text(child))
    return "".join(parts).strip()


def _find_child(block: BlockNode, tag: str):
    for child in block.children:
        if isinstance(child, BlockNode) and child.tag == tag:
            return child
    return None


def _parse_options(raw: str):
    """Baris opsi 'A. teks' -> list (label, teks). Tanpa prefiks: label berurutan."""
    options = []
    next_idx = 0
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([A-Z])[.)]\s*(.*)$", line)
        if m:
            label = m.group(1).upper()
            teks = m.group(2).strip()
            if label in letters:
                next_idx = max(next_idx, letters.index(label) + 1)
        else:
            if next_idx >= len(letters):
                break
            label = letters[next_idx]
            next_idx += 1
            teks = line
        options.append({"label": label, "teks": teks, "is_correct": False})
    return options


def _normalize_legacy(questions: list, tipe: str) -> dict:
    out = []
    for q in questions:
        options = []
        correct = str(q.get("jawaban_benar") or "").strip().upper()
        for letter in "abcde":
            key = f"opsi_{letter}"
            if q.get(key):
                options.append(
                    {
                        "label": letter.upper(),
                        "teks": q[key],
                        "is_correct": letter.upper() == correct,
                    }
                )
        out.append(
            {
                "tipe": tipe,
                "pertanyaan": q.get("pertanyaan", ""),
                "bobot": 1.0,
                "options": options,
                "jawaban_referensi": None,
            }
        )
    return {"tipe": tipe, "questions": out, "items": [{"jenis": "soal", "soal": q} for q in out]}


def _legacy_fallback(raw_text: str) -> dict:
    res = parse_quiz_mcq(raw_text)
    if res["success"] and res["content"]:
        return {"success": True, "content": _normalize_legacy(res["content"], "pilihan_ganda"), "errors": []}
    res2 = parse_quiz_text(raw_text)
    if res2["success"] and res2["content"]:
        return {"success": True, "content": _normalize_legacy(res2["content"], "teks"), "errors": []}
    if not res["success"]:
        return {"success": False, "content": None, "errors": res["errors"]}
    return {"success": False, "content": None, "errors": res2["errors"] or [{"line": 1, "message": "Format kuis tidak dikenali."}]}


def parse_quiz_v2(raw_text: str, expected_type: str | None = None) -> dict:
    """Parse TCML kuis -> struktur ternormalisasi v2.

    expected_type: "pilihan_ganda" | "teks" | None — bila diisi dan [TYPE]
    tidak cocok, hasilnya error (meniru perilaku mismatch v1).
    """
    if "[QUIZ]" not in raw_text.upper():
        return _legacy_fallback(raw_text)

    tokens = Tokenizer(raw_text).tokenize()
    builder = ASTBuilder(tokens)
    root, build_errors = builder.build()
    if build_errors:
        return {"success": False, "content": None, "errors": build_errors}

    quiz_block = None
    for child in root.children:
        if isinstance(child, BlockNode) and child.tag == "QUIZ":
            quiz_block = child
            break
    if quiz_block is None:
        return {"success": False, "content": None, "errors": [{"line": 1, "message": "Missing [QUIZ] root block."}]}

    errors = []
    type_node = _find_child(quiz_block, "TYPE")
    raw_type = _raw_text(type_node).lower() if type_node is not None else ""
    if raw_type in ("pilihan_ganda", "multiple_choice", "mcq"):
        tipe = "pilihan_ganda"
    elif raw_type in ("teks", "essay", "esai", "text"):
        tipe = "teks"
    else:
        errors.append({"line": type_node.line if type_node else 1, "message": "Missing or invalid [TYPE] (pilihan_ganda / essay)."})
        return {"success": False, "content": None, "errors": errors}

    if expected_type and tipe != expected_type:
        errors.append(
            {
                "line": type_node.line if type_node else 1,
                "message": f"Quiz type mismatch: expected {expected_type}, got {tipe}.",
            }
        )
        return {"success": False, "content": None, "errors": errors}

    questions = []
    items = []  # urutan tampil: blok konten (prolog/hint) terseling soal
    for child in quiz_block.children:
        if isinstance(child, TextNode):
            teks_bebas = child.text.strip()
            if teks_bebas:
                items.append({"jenis": "konten", "tipe": "paragraf", "teks": teks_bebas})
            continue
        if not isinstance(child, BlockNode):
            continue
        if child.tag in ("NOTE", "HINT", "EXAMPLE", "WARNING", "SUMMARY"):
            items.append({"jenis": "konten", "tipe": child.tag.lower(), "teks": _raw_text(child)})
            continue
        if child.tag in ("TITLE", "TYPE"):
            continue  # metadata kuis, sudah dibaca di atas
        # Audit #7: blok lain di dalam [QUIZ] TIDAK boleh hilang diam-diam.
        # Dulu [CEK] di kuis / pembungkus [QUESTION] tanpa nomor / salah
        # ketik nama blok terlewat begitu saja dan kuis tersimpan dengan
        # jumlah soal lebih sedikit dari yang ditulis guru.
        if child.tag == "QUESTION":
            errors.append({
                "line": child.line,
                "message": "Pembungkus soal di [QUIZ] wajib bernomor, contoh [QUESTION 1] ... [/QUESTION 1]. [QUESTION] polos adalah tag teks soal DI DALAM pembungkus.",
            })
            continue
        if child.tag == "CEK":
            errors.append({
                "line": child.line,
                "message": "[CEK] adalah soal sisipan untuk MATERI, bukan bagian [QUIZ]. Pindahkan ke dokumen materi, atau ubah menjadi soal [QUESTION n] di kuis ini.",
            })
            continue
        if not (child.tag.startswith("QUESTION") and child.tag != "QUESTION"):
            errors.append({
                "line": child.line,
                "message": f"Blok [{child.tag}] tidak dikenal di dalam [QUIZ] dan tidak dimuat. Periksa nama bloknya.",
            })
            continue
        q_node = _find_child(child, "QUESTION")
        q_text = _raw_text(q_node) if q_node is not None else ""
        if not q_text:
            errors.append({"line": child.line, "message": f"Missing question text in [{child.tag}]."})
            continue

        bobot = 1.0
        w_node = _find_child(child, "WEIGHT")
        if w_node is not None:
            w_raw = _raw_text(w_node)
            try:
                bobot = float(w_raw.replace(",", "."))
                if bobot <= 0:
                    raise ValueError
            except ValueError:
                errors.append({"line": w_node.line, "message": f"Invalid [WEIGHT] value: '{w_raw}'."})
                continue

        answer_node = _find_child(child, "ANSWER")
        answer_raw = _raw_text(answer_node) if answer_node is not None else ""

        if tipe == "pilihan_ganda":
            opt_node = _find_child(child, "OPTIONS")
            options = _parse_options(_raw_text(opt_node)) if opt_node is not None else []
            if len(options) < 2:
                errors.append({"line": child.line, "message": f"Question [{child.tag}] needs at least 2 options in [OPTIONS]."})
                continue
            labels = {o["label"] for o in options}
            correct = [t.upper() for t in re.split(r"[,\s]+", answer_raw) if t.strip()]
            if not correct:
                errors.append({"line": child.line, "message": f"Missing [ANSWER] for [{child.tag}]."})
                continue
            bad = [c for c in correct if c not in labels]
            if bad:
                errors.append({"line": child.line, "message": f"Answer label(s) {', '.join(bad)} not in options for [{child.tag}]."})
                continue
            for o in options:
                o["is_correct"] = o["label"] in correct
            soal = {"tipe": tipe, "pertanyaan": q_text, "bobot": bobot, "options": options, "jawaban_referensi": None}
            questions.append(soal)
            items.append({"jenis": "soal", "soal": soal})
        else:
            soal = {
                "tipe": tipe,
                "pertanyaan": q_text,
                "bobot": bobot,
                "options": [],
                "jawaban_referensi": answer_raw or None,
            }
            questions.append(soal)
            items.append({"jenis": "soal", "soal": soal})

    if errors:
        return {"success": False, "content": None, "errors": errors}
    if not questions:
        return {"success": False, "content": None, "errors": [{"line": 1, "message": "No questions found in [QUIZ]."}]}
    return {"success": True, "content": {"tipe": tipe, "questions": questions, "items": items}, "errors": []}
