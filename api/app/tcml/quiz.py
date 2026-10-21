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

import math
import re

from .core import ASTBuilder, BlockNode, TextNode, Tokenizer
from .engine import parse_quiz_mcq, parse_quiz_text


# ---------------------------------------------------------- normalisasi AI
# Model AI (terutama yang lebih kecil) sangat sering menulis kuis dalam
# "format datar": [QUESTION] polos sebagai pembungkus dengan [OPTIONS]/
# [ANSWER] sebagai saudaranya — padahal format kanonis menuntut pembungkus
# bernomor [QUESTION n]. Kesalahan ini murni mekanis, jadi diperbaiki
# secara DETERMINISTIK di sini (bukan dengan meminta AI menulis ulang):
# soal datar dikelompokkan menjadi pembungkus bernomor, dan seluruh
# pembungkus dinomori ulang berurutan dari 1 (aturan audit #38).
_TAG_TOKEN_RE = re.compile(r"\[/?[A-Z]+(?:\s+\d+)?\]")
_QUIZ_SPAN_RE = re.compile(r"\[QUIZ\]([\s\S]*?)\[/QUIZ\]")
_WRAPPER_RE = re.compile(r"^\[QUESTION\s+(\d+)\]")
_BLOK_SOAL_RE = {
    nama: re.compile(rf"\[{nama}\]([\s\S]*?)\[/{nama}\]")
    for nama in ("QUESTION", "OPTIONS", "ANSWER", "WEIGHT")
}


def _segmen_level_atas(body: str) -> list[str]:
    """Pecah isi root menjadi segmen blok level atas (sadar kedalaman)."""
    segmen: list[str] = []
    buf: list[str] = []
    depth = 0
    dalam_blok = False
    pos = 0
    for m in _TAG_TOKEN_RE.finditer(body):
        buf.append(body[pos : m.start()])
        tok = m.group(0)
        buf.append(tok)
        if tok.startswith("[/"):
            depth = max(0, depth - 1)
        else:
            depth += 1
            dalam_blok = True
        pos = m.end()
        if dalam_blok and depth == 0:
            segmen.append("".join(buf))
            buf = []
            dalam_blok = False
    buf.append(body[pos:])
    sisa = "".join(buf)
    if sisa:
        segmen.append(sisa)
    return segmen


def _urai_unit_datar(segmen_unit: list[str]) -> str | None:
    """Susun ulang unit soal datar menjadi isi pembungkus kanonis:
    [QUESTION]teks[/QUESTION] + [OPTIONS]? + [ANSWER]? + [WEIGHT]?.
    Mengembalikan None bila blok [QUESTION] tidak ditemukan."""
    gabungan = "\n".join(segmen_unit)
    q = _BLOK_SOAL_RE["QUESTION"].search(gabungan)
    if q is None:
        return None
    teks_soal = q.group(1)
    # Varian bersarang: OPTIONS/ANSWER tertulis DI DALAM blok [QUESTION].
    ekstra: dict[str, str] = {}
    for nama in ("OPTIONS", "ANSWER", "WEIGHT"):
        m = _BLOK_SOAL_RE[nama].search(teks_soal)
        if m is not None:
            ekstra[nama] = m.group(0)
            teks_soal = (teks_soal[: m.start()] + teks_soal[m.end() :]).strip()
    blok = [f"[QUESTION]{teks_soal.strip()}[/QUESTION]"]
    for nama in ("OPTIONS", "ANSWER", "WEIGHT"):
        if nama in ekstra:
            blok.append(ekstra[nama])
            continue
        m = _BLOK_SOAL_RE[nama].search(gabungan)
        if m is not None:
            blok.append(m.group(0))
    return "\n".join(blok)


def normalisasi_format_kuis(teks: str) -> str:
    """Perbaiki format kuis datar keluaran AI menjadi format kanonis.

    - Soal [QUESTION] polos + saudara [OPTIONS]/[ANSWER]/[WEIGHT] di
      level root [QUIZ] dibungkus menjadi [QUESTION n] ... [/QUESTION n].
    - Semua pembungkus (lama & baru) dinomori ulang berurutan dari 1.
    - Teks tanpa [QUIZ], atau yang sudah kanonis, dikembalikan apa adanya.
    Tipe kuis TIDAK diubah — mismatch tipe adalah kesalahan isi, bukan
    format, dan ditangani prompt + repair.
    """
    m = _QUIZ_SPAN_RE.search(teks)
    if m is None:
        return teks
    segmen = _segmen_level_atas(m.group(1))
    keluaran: list[str] = []
    unit_datar: list[str] | None = None
    nomor = 0
    berubah = False

    def tutup_unit() -> None:
        nonlocal unit_datar, nomor, berubah
        if unit_datar is not None:
            isi = _urai_unit_datar(unit_datar)
            if isi is not None:
                nomor += 1
                keluaran.append(f"[QUESTION {nomor}]\n{isi}\n[/QUESTION {nomor}]")
                berubah = True
            else:
                keluaran.extend(unit_datar)
            unit_datar = None

    for seg in segmen:
        s = seg.strip()
        if _WRAPPER_RE.match(s):
            tutup_unit()
            nomor += 1
            seg_baru = re.sub(r"\[QUESTION\s+\d+\]", f"[QUESTION {nomor}]", seg, count=1)
            seg_baru = re.sub(r"\[/QUESTION\s+\d+\]", f"[/QUESTION {nomor}]", seg_baru, count=1)
            if seg_baru != seg:
                berubah = True
            keluaran.append(seg_baru)
        elif s.startswith("[QUESTION]"):
            tutup_unit()
            unit_datar = [seg]
        elif unit_datar is not None and (
            s.startswith("[OPTIONS]") or s.startswith("[ANSWER]") or s.startswith("[WEIGHT]")
        ):
            unit_datar.append(seg)
        else:
            tutup_unit()
            keluaran.append(seg)
    tutup_unit()
    if not berubah:
        return teks
    return teks[: m.start(1)] + "".join(keluaran) + teks[m.end(1) :]


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
    options, _ = _parse_options_checked(raw)
    return options


def _parse_options_checked(raw: str):
    """Seperti _parse_options, plus pesan error (audit #15/#38): label ganda
    dan opsi tanpa label melebihi Z TIDAK lagi diterima/dipotong diam-diam."""
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
                return options, "Jumlah opsi melebihi 26 (label A–Z). Kurangi opsi atau beri label huruf secara eksplisit."
            label = letters[next_idx]
            next_idx += 1
            teks = line
        options.append({"label": label, "teks": teks, "is_correct": False})
    labels = [o["label"] for o in options]
    ganda = sorted({l for l in labels if labels.count(l) > 1})
    if ganda:
        return options, f"Label opsi ganda: {', '.join(ganda)} — setiap opsi wajib berlabel unik."
    return options, None


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


def _legacy_fallback(raw_text: str, expected_type: str | None = None) -> dict:
    """Fallback format legacy v1. Audit #30: tipe hasil fallback WAJIB
    cocok dengan expected_type — dulu kuis esai yang diminta bisa kembali
    sebagai PG (atau sebaliknya) dan Quiz.tipe berbeda dari soal-soalnya."""
    res = parse_quiz_mcq(raw_text)
    if res["success"] and res["content"]:
        if expected_type and expected_type != "pilihan_ganda":
            return {
                "success": False,
                "content": None,
                "errors": [{"line": 1, "message": f"Quiz type mismatch: expected {expected_type}, got pilihan_ganda (format legacy)."}],
            }
        return {"success": True, "content": _normalize_legacy(res["content"], "pilihan_ganda"), "errors": []}
    res2 = parse_quiz_text(raw_text)
    if res2["success"] and res2["content"]:
        if expected_type and expected_type != "teks":
            return {
                "success": False,
                "content": None,
                "errors": [{"line": 1, "message": f"Quiz type mismatch: expected {expected_type}, got teks (format legacy)."}],
            }
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
        return _legacy_fallback(raw_text, expected_type)

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
    nomor_diharapkan = 1  # audit #38: pembungkus soal wajib berurutan 1,2,3,...
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
        # Audit #38: nomor pembungkus wajib angka & berurutan dari 1.
        akhiran = child.tag[len("QUESTION"):].strip()
        if not akhiran.isdigit():
            errors.append({
                "line": child.line,
                "message": f"Pembungkus soal [{child.tag}] tidak valid — nomor soal wajib angka, contoh [QUESTION 1].",
            })
            continue
        if int(akhiran) != nomor_diharapkan:
            errors.append({
                "line": child.line,
                "message": f"Nomor soal tidak berurutan: ditemukan [QUESTION {akhiran}], seharusnya [QUESTION {nomor_diharapkan}].",
            })
            continue
        nomor_diharapkan += 1
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
                if bobot <= 0 or not math.isfinite(bobot):
                    raise ValueError
            except ValueError:
                errors.append({"line": w_node.line, "message": f"Invalid [WEIGHT] value: '{w_raw}'."})
                continue

        answer_node = _find_child(child, "ANSWER")
        answer_raw = _raw_text(answer_node) if answer_node is not None else ""

        if tipe == "pilihan_ganda":
            opt_node = _find_child(child, "OPTIONS")
            options, opsi_error = _parse_options_checked(_raw_text(opt_node)) if opt_node is not None else ([], None)
            if opsi_error:
                errors.append({"line": child.line, "message": f"Question [{child.tag}]: {opsi_error}"})
                continue
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
