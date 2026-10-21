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
    "dokumen": "dokumen terpadu (materi + kuis)",
}
KIND_ROOTS = {
    "materi": {"MATERIAL", "EXERCISE", "PROJECT"},
    "kuis_pg": {"QUIZ"},
    "kuis_esai": {"QUIZ"},
    "dokumen": {"MATERIAL", "EXERCISE", "PROJECT", "QUIZ"},
}
KIND_QUIZ_TIPE = {"kuis_pg": "pilihan_ganda", "kuis_esai": "teks"}


# ------------------------------------------------------------- modul & paket
def sync_tag_modules(db: Session, commit: bool = True) -> dict[str, TagModule]:
    """Samakan tabel tag_modules/tag_examples dengan registry kode (idempoten).

    Audit #28: pemanggil yang sedang di tengah transaksi (buat/ubah paket)
    wajib memakai commit=False — commit di tengah handler membuat data
    tersimpan SEBAGIAN walaupun validasi sesudahnya gagal (400)."""
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
    if commit:
        db.commit()
    else:
        db.flush()
    return {m.slug: m for m in db.query(TagModule).all()}


# Paket bawaan (blueprint Bagian 14): dibuat otomatis per guru saat pertama
# kali membuka daftar paketnya, agar tidak mulai dari halaman kosong.
PRESET_PACKS = [
    ("Mapel Umum", "Paket serbaguna untuk materi pelajaran umum.", ["inti-materi", "tabel-data", "latihan"]),
    ("Spreadsheet & Data", "Materi berbasis tabel, dataset, dan rumus.", ["inti-materi", "tabel-data", "formula-kode"]),
    ("Pemrograman", "Materi coding: kode, latihan praktik, dan proyek.", ["inti-materi", "formula-kode", "latihan", "proyek"]),
    ("Kuis Pilihan Ganda", "Khusus menyusun kuis PG berbobot & multi-jawaban.", ["kuis-pg"]),
    ("Kuis Esai", "Khusus menyusun kuis esai dengan jawaban referensi.", ["kuis-esai"]),
    ("Kelas Lengkap", "Semua modul: materi, data, kode, latihan, proyek, cek pemahaman, dan kedua kuis.", ["inti-materi", "tabel-data", "formula-kode", "latihan", "proyek", "cek-pemahaman", "kuis-pg", "kuis-esai"]),
    ("Kursus Scratch", "Paket kelas coding Scratch: materi dengan sematan proyek & blok visual, latihan, tugas proyek (.sb3), dan kuis PG.", ["inti-materi", "scratch", "latihan", "proyek", "kuis-pg"]),
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
    # Paket "Kelas Lengkap" = SEMUA modul menurut definisinya: lengkapi
    # modul cek-pemahaman pada paket lama yang belum memuatnya — SEKALI
    # saja (audit #35). Bendera topup_cek_v1 (migrasi 0008) memastikan
    # modul yang SENGAJA dilepas guru sesudahnya tidak dibangkitkan lagi
    # setiap membuka daftar paket.
    lengkap = (
        db.query(ParserPack)
        .filter(ParserPack.dibuat_oleh == user.id, ParserPack.nama == "Kelas Lengkap")
        .first()
    )
    if lengkap is not None and not lengkap.topup_cek_v1:
        from .models import ParserPackModule

        if "cek-pemahaman" in modules:
            ada = {
                pm.module_id
                for pm in db.query(ParserPackModule).filter(ParserPackModule.pack_id == lengkap.id).all()
            }
            if modules["cek-pemahaman"].id not in ada:
                urutan = max((pm.urutan for pm in db.query(ParserPackModule).filter(ParserPackModule.pack_id == lengkap.id).all()), default=-1) + 1
                db.add(ParserPackModule(pack_id=lengkap.id, module_id=modules["cek-pemahaman"].id, urutan=urutan))
        lengkap.topup_cek_v1 = True
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


def normalize_tag_pilihan(raw) -> Optional[dict]:
    """Validasi & rapikan pilihan tag per modul ({"slug": ["TAG", ...]}).

    Mengembalikan None bila tidak ada pilihan efektif. ValueError (pesan
    Bahasa Indonesia) untuk slug/tag yang tidak dikenal.
    """
    if not raw:
        return None
    out: dict[str, list[str]] = {}
    for slug, tags in raw.items():
        meta = MODULES.get(slug)
        if meta is None:
            raise ValueError(f"Modul tidak dikenal: {slug}")
        valid = set(meta["tags"])
        chosen: list[str] = []
        for t in tags or []:
            if t not in valid:
                raise ValueError(f"Tag [{t}] tidak termasuk modul {meta['nama']}.")
            if t not in chosen:
                chosen.append(t)
        if chosen:
            out[slug] = chosen
    return out or None


def effective_tag_pilihan(slugs: list[str], tag_pilihan) -> Optional[dict]:
    """Pilihan tag efektif: eksplisit bila ada, selain itu semua tag modul."""
    if tag_pilihan:
        return normalize_tag_pilihan(tag_pilihan)
    return {s: list(MODULES[s]["tags"]) for s in slugs if s in MODULES} or None


def allowed_tags_for_pack(db: Session, pack: ParserPack) -> set[str]:
    """Tag yang diizinkan paket: per tag bila tag_pilihan ada, else per modul."""
    if pack.tag_pilihan:
        allowed = set(ROOT_BLOCKS)
        for tags in pack.tag_pilihan.values():
            allowed.update(tags)
        return allowed
    return allowed_tags_for(pack_module_rows(db, pack))


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
def spec_text_for_selection(
    db: Session, slugs: list[str], tag_pilihan: Optional[dict]
) -> str:
    """Rakit teks spec dari pilihan modul/tag (dipakai paket tersimpan,
    pratinjau, dan meja uji). Bila tag_pilihan ada, spec disusun per tag
    dari metadata registry; selain itu fragmen spec modul utuh (klasik)."""
    rows_by_slug = sync_tag_modules(db)
    parts = []
    for slug in slugs:
        m = rows_by_slug.get(slug)
        if m is None:
            continue
        meta = MODULES.get(slug, {})
        parts.append(f"## Modul: {m.nama}")
        if m.deskripsi:
            parts.append(m.deskripsi)
        if tag_pilihan:
            intro = meta.get("spec_intro")
            if intro:
                parts.append(intro)
            meta_tags = meta.get("tags_meta", {})
            for tag in tag_pilihan.get(slug, []):
                tm = meta_tags.get(tag)
                if tm:
                    parts.append(tm["spec"])
        elif m.spec_fragment:
            parts.append(m.spec_fragment)
        for ex in sorted(m.examples, key=lambda e: e.urutan):
            parts.append(f"Contoh — {ex.judul}:\n```\n{ex.konten}\n```")
        parts.append("")
    return "\n".join(parts).strip()


def build_spec_text(db: Session, pack: ParserPack) -> str:
    """Teks spesifikasi paket: hanya modul/tag terpilih (hemat konteks AI)."""
    slugs = [m.slug for m in pack_module_rows(db, pack)]
    return spec_text_for_selection(db, slugs, pack.tag_pilihan)


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


_ROOT_OPEN_ANY = re.compile(r"\[(MATERIAL|EXERCISE|PROJECT|QUIZ)\]")


def split_documents(raw: str) -> list[str]:
    """Pecah keluaran AI menjadi dokumen per root block.

    Baris fence ``` dibuang; teks di luar root block diabaikan.
    Audit #16: tag buka/tutup akar boleh SEBARIS dengan teks lain — dulu
    penutup yang tidak sendirian sebaris membuat sisa dokumen hilang.
    """
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("```")]
    docs: list[str] = []
    current: Optional[list[str]] = None
    root: Optional[str] = None
    for ln in lines:
        sisa = ln
        # Satu baris bisa menutup akar lama DAN membuka akar baru.
        while True:
            if current is None:
                opened = _ROOT_OPEN_ANY.search(sisa)
                if not opened:
                    break
                root = opened.group(1)
                current = [sisa[opened.start():]]
                sisa = ""
                # Akar yang buka & tutup sebaris ditangani loop berikutnya.
                if f"[/{root}]" not in current[0]:
                    break
                sisa = current[0]
                current = []
            penutup = f"[/{root}]"
            idx = sisa.find(penutup)
            if idx < 0:
                if sisa:
                    current.append(sisa)
                break
            current.append(sisa[: idx + len(penutup)])
            docs.append("\n".join(current).strip())
            current = None
            sisa = sisa[idx + len(penutup):]
            root = None
            if not sisa.strip():
                break
    return docs


def extract_tags(teks: str) -> set[str]:
    """Tag yang dipakai dokumen, dari POHON AST (audit #17).

    Dulu regex atas teks mentah: tag contoh di dalam [CODE]/blok mentah
    ikut terhitung (dokumen sah ditolak) — sekarang sub-pohon blok mentah
    dilewati, sama seperti ekstraksi [CEK]. Bila AST gagal dibangun,
    kembali ke regex (dokumennya toh gugur di lapis 1).
    """
    from .tcml.cek import RAW_BLOCK_TAGS
    from .tcml.core import ASTBuilder, BlockNode, Tokenizer

    tokens = Tokenizer(teks).tokenize()
    ast, build_errors = ASTBuilder(tokens).build()
    if build_errors:
        tags: set[str] = set()
        for m in _TAG_RE.finditer(teks):
            name = m.group(2)
            if name == "QUESTION" and m.group(3):
                tags.add("QUESTION_BLOCK")
            else:
                tags.add(name)
        return tags
    tags = set()

    def jalan(node, dalam_mentah: bool) -> None:
        for child in node.children:
            if not isinstance(child, BlockNode):
                continue
            if not dalam_mentah:
                potong = child.tag.split(None, 1)
                nama = potong[0]
                if nama == "QUESTION" and len(potong) == 2:
                    tags.add("QUESTION_BLOCK")
                else:
                    tags.add(nama)
            jalan(child, dalam_mentah or child.tag in RAW_BLOCK_TAGS)

    jalan(ast, False)
    return tags


def _akar_bersarang(teks: str) -> list[str]:
    """Nama akar dokumen yang muncul BERSARANG di dalam blok lain (audit
    #17) — mis. [QUIZ] di dalam [MATERIAL] tidak pernah dirender sebagai
    kuis dan harus ditolak, bukan lolos diam-diam. Isi blok mentah dikecualikan."""
    from .tcml.cek import RAW_BLOCK_TAGS
    from .tcml.core import ASTBuilder, BlockNode, Tokenizer

    tokens = Tokenizer(teks).tokenize()
    ast, build_errors = ASTBuilder(tokens).build()
    if build_errors:
        return []
    ditemukan: list[str] = []

    def jalan(node, kedalaman: int, dalam_mentah: bool) -> None:
        for child in node.children:
            if not isinstance(child, BlockNode):
                continue
            nama = child.tag.split(None, 1)[0]
            if kedalaman > 0 and not dalam_mentah and nama in ROOT_BLOCKS and nama not in ditemukan:
                ditemukan.append(nama)
            jalan(child, kedalaman + 1, dalam_mentah or child.tag in RAW_BLOCK_TAGS)

    jalan(ast, 0, False)
    return ditemukan


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

    # --- lapis 2b: tag harus dari modul/tag pilihan paket
    allowed = allowed_tags_for_pack(db, pack)
    for tag in sorted(extract_tags(teks) - allowed):
        errors.append(
            {"lapis": "skema", "message": f"Tag [{tag}] tidak termasuk modul paket ini."}
        )
    # --- lapis 2c (audit #17): akar bersarang & [TITLE] wajib untuk materi
    for nama in _akar_bersarang(teks):
        errors.append(
            {"lapis": "skema", "message": f"Akar [{nama}] bersarang di dalam blok lain — akar dokumen harus di tingkat teratas."}
        )
    if root in ("MATERIAL", "EXERCISE", "PROJECT") and "TITLE" not in extract_tags(teks):
        errors.append(
            {"lapis": "skema", "message": "Dokumen materi wajib memiliki [TITLE] (tag wajib pada modul materi)."}
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


def validate_bundle_document(db: Session, pack: ParserPack, teks: str) -> dict:
    """Validasi 2 lapis DOKUMEN TERPADU (satu teks: bagian materi + kuis).

    Lapis 1: tiap bagian harus lolos parser-nya (pemecahan memakai
    tcml.document.split_document; bagian materi diperiksa parse_material,
    bagian kuis sudah diperiksa parse_quiz_v2 oleh pemecah).
    Lapis 2: root tiap bagian harus diizinkan paket; semua tag yang dipakai
    harus berasal dari modul/tag pilihan paket.
    """
    from .tcml.document import split_document

    parts = split_document(teks)
    errors: list[dict] = [
        {"lapis": "sintaks", "line": e.get("line"), "message": e["message"]}
        for e in parts["errors"]
    ]
    if not any(parts[k] for k in ("materi", "kuis_pg", "kuis_esai")):
        errors.append(
            {"lapis": "skema", "message": "Tidak ada bagian materi maupun kuis yang terbaca dari dokumen."}
        )

    if parts["materi"]:
        m = re.search(r"\[(MATERIAL|EXERCISE|PROJECT)\]", parts["materi"])
        root_materi = m.group(1) if m else None
        if pack.allowed_roots and root_materi not in pack.allowed_roots:
            errors.append(
                {"lapis": "skema", "message": f"Root [{root_materi}] tidak diizinkan paket ini (diizinkan: {', '.join(pack.allowed_roots)})."}
            )
        res = parse_material(parts["materi"])
        if not res["success"]:
            for e in res["errors"]:
                errors.append({"lapis": "sintaks", "line": e.get("line"), "message": e["message"]})
    if (parts["kuis_pg"] or parts["kuis_esai"]) and pack.allowed_roots and "QUIZ" not in pack.allowed_roots:
        errors.append(
            {"lapis": "skema", "message": "Dokumen berisi kuis, tetapi root [QUIZ] tidak diizinkan paket ini."}
        )

    allowed = allowed_tags_for_pack(db, pack)
    for tag in sorted(extract_tags(teks) - allowed):
        errors.append(
            {"lapis": "skema", "message": f"Tag [{tag}] tidak termasuk modul paket ini."}
        )
    for nama in _akar_bersarang(teks):
        errors.append(
            {"lapis": "skema", "message": f"Akar [{nama}] bersarang di dalam blok lain — akar dokumen harus di tingkat teratas."}
        )

    judul = _extract_title(parts["materi"] or "") or "Dokumen hasil generate"
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "judul": judul,
        "parts": parts,
    }
