"""Layanan Paket Parser & Generate AI (Fase 5).

Satu tempat untuk: sinkronisasi modul tag dari registry kode ke DB,
rakitan prompt/ekspor dari modul terpilih saja, pemecahan bundle keluaran AI
menjadi dokumen-dokumen, dan validasi 2 lapis (sintaks TCML + skema paket).
"""

import re
from typing import Optional

from sqlalchemy.orm import Session

from .models import ParserPack, ParserPackShare, TagExample, TagModule, User
from .tcml import parse_material
from .tcml.quiz import parse_quiz_v2
from .tcml.registry import MODULES, ROOT_BLOCKS

KIND_LABEL = {
    "materi": "materi/latihan/proyek",
    "kuis_pg": "kuis pilihan ganda",
    "kuis_esai": "kuis esai",
}
KIND_ROOTS = {
    "materi": {"MATERIAL", "EXERCISE", "PROJECT"},
    "kuis_pg": {"QUIZ"},
    "kuis_esai": {"QUIZ"},
}
KIND_QUIZ_TIPE = {"kuis_pg": "pilihan_ganda", "kuis_esai": "teks"}


# ------------------------------------------------------------- modul & paket
def sync_tag_modules(db: Session) -> dict[str, TagModule]:
    """Samakan tabel tag_modules/tag_examples dengan registry kode (idempoten)."""
    for slug, meta in MODULES.items():
        row = db.query(TagModule).filter(TagModule.slug == slug).first()
        if row is None:
            row = TagModule(slug=slug, nama=meta["nama"])
            db.add(row)
            db.flush()
        row.nama = meta["nama"]
        row.deskripsi = meta.get("deskripsi")
        row.spec_fragment = meta.get("spec", "")
        row.is_system = True
        for ex in list(row.examples):
            db.delete(ex)
        db.flush()
        for i, ex in enumerate(meta.get("contoh", [])):
            db.add(
                TagExample(
                    module_id=row.id, judul=ex["judul"], konten=ex["konten"], urutan=i
                )
            )
    db.commit()
    return {m.slug: m for m in db.query(TagModule).all()}


# Paket bawaan (blueprint Bagian 14): dibuat otomatis per guru saat pertama
# kali membuka daftar paketnya, agar tidak mulai dari halaman kosong.
PRESET_PACKS = [
    ("Mapel Umum", "Paket serbaguna untuk materi pelajaran umum.", ["inti-materi", "tabel-data", "latihan"]),
    ("Spreadsheet & Data", "Materi berbasis tabel, dataset, dan rumus.", ["inti-materi", "tabel-data", "formula-kode"]),
    ("Pemrograman", "Materi coding: kode, latihan praktik, dan proyek.", ["inti-materi", "formula-kode", "latihan", "proyek"]),
    ("Kuis Pilihan Ganda", "Khusus menyusun kuis PG berbobot & multi-jawaban.", ["kuis-pg"]),
    ("Kuis Esai", "Khusus menyusun kuis esai dengan jawaban referensi.", ["kuis-esai"]),
    ("Kelas Lengkap", "Semua modul: materi, data, kode, latihan, proyek, dan kedua kuis.", ["inti-materi", "tabel-data", "formula-kode", "latihan", "proyek", "kuis-pg", "kuis-esai"]),
]


def ensure_preset_packs(db: Session, user: User) -> None:
    """Buat paket bawaan untuk user bila belum punya (berdasarkan nama)."""
    from .models import ParserPackModule

    modules = sync_tag_modules(db)
    existing = {
        p.nama
        for p in db.query(ParserPack).filter(ParserPack.dibuat_oleh == user.id).all()
    }
    created = False
    for nama, deskripsi, slugs in PRESET_PACKS:
        if nama in existing:
            continue
        pack = ParserPack(
            nama=nama,
            deskripsi=deskripsi,
            dibuat_oleh=user.id,
            visibilitas="private",
            allowed_roots=roots_for_slugs(slugs),
        )
        db.add(pack)
        db.flush()
        for i, slug in enumerate(slugs):
            db.add(
                ParserPackModule(pack_id=pack.id, module_id=modules[slug].id, urutan=i)
            )
        created = True
    if created:
        db.commit()


def pack_module_rows(db: Session, pack: ParserPack) -> list[TagModule]:
    from .models import ParserPackModule

    rows = (
        db.query(TagModule)
        .join(ParserPackModule, ParserPackModule.module_id == TagModule.id)
        .filter(ParserPackModule.pack_id == pack.id)
        .order_by(ParserPackModule.urutan)
        .all()
    )
    return rows


def allowed_tags_for(modules: list[TagModule]) -> set[str]:
    allowed = set(ROOT_BLOCKS)
    for m in modules:
        allowed.update(MODULES.get(m.slug, {}).get("tags", []))
    return allowed


def roots_for_slugs(slugs: list[str]) -> list[str]:
    roots: list[str] = []
    for slug in slugs:
        for r in MODULES.get(slug, {}).get("roots", []):
            if r not in roots:
                roots.append(r)
    return roots


def pack_shares(db: Session, pack: ParserPack) -> list[ParserPackShare]:
    return db.query(ParserPackShare).filter(ParserPackShare.pack_id == pack.id).all()


def can_access_pack(db: Session, user: User, pack: ParserPack) -> bool:
    if user.role == "admin" or pack.dibuat_oleh == user.id:
        return True
    share = (
        db.query(ParserPackShare)
        .filter(
            ParserPackShare.pack_id == pack.id,
            (ParserPackShare.shared_with_id == user.id)
            | (ParserPackShare.shared_with_id.is_(None)),
        )
        .first()
    )
    return share is not None


# ------------------------------------------------------------ rakitan prompt
def build_spec_text(db: Session, pack: ParserPack) -> str:
    """Teks spesifikasi paket: hanya modul terpilih (hemat konteks AI)."""
    parts = []
    for m in pack_module_rows(db, pack):
        parts.append(f"## Modul: {m.nama}")
        if m.deskripsi:
            parts.append(m.deskripsi)
        if m.spec_fragment:
            parts.append(m.spec_fragment)
        for ex in sorted(m.examples, key=lambda e: e.urutan):
            parts.append(f"Contoh — {ex.judul}:\n```\n{ex.konten}\n```")
        parts.append("")
    return "\n".join(parts).strip()


def build_system_prompt(db: Session, pack: ParserPack, kind: str) -> str:
    roots = ", ".join(f"[{r}]" for r in (pack.allowed_roots or []))
    return (
        "Kamu adalah penulis konten pembelajaran untuk LMS Lifunze. Kamu menulis konten "
        "dalam format TCML (markup berbasis tag kurung siku) sesuai spesifikasi paket parser berikut.\n\n"
        "ATURAN OUTPUT:\n"
        "- Keluarkan HANYA dokumen TCML. Boleh membungkus keluaran dalam fence ```tcml. "
        "Jangan menulis penjelasan, pembuka, atau penutup di luar dokumen.\n"
        "- Kamu BOLEH menghasilkan beberapa dokumen sekaligus (bundle); tulis tiap dokumen "
        "dengan root block-nya sendiri secara berurutan.\n"
        f"- Root block yang diizinkan paket ini: {roots}.\n"
        "- Gunakan HANYA tag yang ada pada modul-modul paket di bawah ini.\n"
        "- Bahasa konten: Bahasa Indonesia.\n\n"
        f"{build_spec_text(db, pack)}"
    )


def build_export_markdown(db: Session, pack: ParserPack, owner_name: str) -> str:
    roots = ", ".join(f"[{r}]" for r in (pack.allowed_roots or []))
    return (
        f"# Paket Parser TCML: {pack.nama}\n\n"
        f"{pack.deskripsi or ''}\n\n"
        f"- Pemilik: {owner_name}\n"
        f"- Root block yang diizinkan: {roots}\n\n"
        "## Cara memakai paket ini di LLM eksternal\n\n"
        "Tempel SELURUH isi file ini sebagai pesan pertama/system prompt, lalu sampaikan "
        "permintaan kontenmu (topik, jenjang, jumlah soal, dst). Keluaran AI berupa dokumen "
        "TCML dapat ditempel ke editor Lifunze (materi/kuis) atau lewat fitur Generate AI.\n\n"
        "## Aturan output untuk AI\n\n"
        "- Keluarkan HANYA dokumen TCML (boleh dalam fence ```tcml), tanpa penjelasan lain.\n"
        "- Boleh beberapa dokumen sekaligus; tiap dokumen dengan root block-nya sendiri.\n"
        "- Gunakan HANYA tag dari modul-modul di bawah ini.\n"
        "- Bahasa konten: Bahasa Indonesia.\n\n"
        f"{build_spec_text(db, pack)}\n"
    )


# ------------------------------------------------------ bundle & validasi AI
_ROOT_OPEN = re.compile(r"^\s*\[(MATERIAL|EXERCISE|PROJECT|QUIZ)\]\s*$")
_ROOT_CLOSE = re.compile(r"^\s*\[/(MATERIAL|EXERCISE|PROJECT|QUIZ)\]\s*$")
_TAG_RE = re.compile(r"\[(/?)([A-Z][A-Z0-9_]*)(?:\s+(\d+))?\]")


def split_documents(raw: str) -> list[str]:
    """Pecah keluaran AI menjadi dokumen per root block.

    Baris fence ``` dibuang; teks di luar root block diabaikan.
    """
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("```")]
    docs: list[str] = []
    current: Optional[list[str]] = None
    root: Optional[str] = None
    for ln in lines:
        opened = _ROOT_OPEN.match(ln)
        if opened and current is None:
            current = [ln]
            root = opened.group(1)
            continue
        if current is not None:
            current.append(ln)
            closed = _ROOT_CLOSE.match(ln)
            if closed and closed.group(1) == root:
                docs.append("\n".join(current).strip())
                current = None
                root = None
    return docs


def extract_tags(teks: str) -> set[str]:
    tags: set[str] = set()
    for m in _TAG_RE.finditer(teks):
        name = m.group(2)
        if name == "QUESTION" and m.group(3):
            tags.add("QUESTION_BLOCK")
        else:
            tags.add(name)
    return tags


def _extract_title(teks: str) -> Optional[str]:
    m = re.search(r"\[TITLE\](.*?)\[/TITLE\]", teks, re.DOTALL)
    if m:
        return " ".join(m.group(1).split())[:200]
    return None


def validate_document(db: Session, pack: ParserPack, kind: str, teks: str) -> dict:
    """Validasi 2 lapis satu dokumen hasil AI terhadap paket & jenis permintaan.

    Lapis 1 (sintaks): parser TCML/kuis v2 harus berhasil.
    Lapis 2 (skema): root termasuk allowed_roots paket & sesuai jenis yang
    diminta; semua tag yang dipakai harus berasal dari modul paket.
    """
    errors: list[dict] = []
    m = re.search(r"\[(MATERIAL|EXERCISE|PROJECT|QUIZ)\]", teks)
    root = m.group(1) if m else None
    if root is None:
        return {
            "root": None,
            "jenis": None,
            "tipe_quiz": None,
            "judul": "(tanpa judul)",
            "valid": False,
            "errors": [{"lapis": "skema", "message": "Dokumen tidak memiliki root block [MATERIAL]/[EXERCISE]/[PROJECT]/[QUIZ]."}],
        }

    jenis = "quiz" if root == "QUIZ" else "material"
    tipe_quiz: Optional[str] = None

    # --- lapis 2a: kesesuaian jenis & allowed roots
    if root not in KIND_ROOTS[kind]:
        errors.append(
            {
                "lapis": "skema",
                "message": f"Root [{root}] tidak sesuai jenis yang diminta ({KIND_LABEL[kind]}).",
            }
        )
    if pack.allowed_roots and root not in pack.allowed_roots:
        errors.append(
            {
                "lapis": "skema",
                "message": f"Root [{root}] tidak diizinkan paket ini (diizinkan: {', '.join(pack.allowed_roots)}).",
            }
        )

    # --- lapis 1: sintaks
    if root == "QUIZ":
        res = parse_quiz_v2(teks, expected_type=KIND_QUIZ_TIPE.get(kind))
        if res["success"]:
            tipe_quiz = res["content"]["tipe"]
        else:
            for e in res["errors"]:
                errors.append({"lapis": "sintaks", "line": e.get("line"), "message": e["message"]})
    else:
        res = parse_material(teks)
        if not res["success"]:
            for e in res["errors"]:
                errors.append({"lapis": "sintaks", "line": e.get("line"), "message": e["message"]})

    # --- lapis 2b: tag harus dari modul paket
    modules = pack_module_rows(db, pack)
    allowed = allowed_tags_for(modules)
    for tag in sorted(extract_tags(teks) - allowed):
        errors.append(
            {"lapis": "skema", "message": f"Tag [{tag}] tidak termasuk modul paket ini."}
        )

    judul = _extract_title(teks)
    if not judul:
        judul = "Kuis hasil generate" if jenis == "quiz" else "(tanpa judul)"
    return {
        "root": root,
        "jenis": jenis,
        "tipe_quiz": tipe_quiz,
        "judul": judul,
        "valid": len(errors) == 0,
        "errors": errors,
    }
