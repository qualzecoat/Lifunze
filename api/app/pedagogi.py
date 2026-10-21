"""Template Alur Mengajar (Pedagogi) — gabungan paket+pedagogi 2026-10-21.

Keputusan desain (disepakati Qualze):
- Template dan paket DIPISAH sebagai data: template MERUJUK paket.
  Untuk guru tampil menyatu ("pilih alur, selesai"); fondasinya terpisah
  agar alur bisa dipasangkan dengan paket kustom apa pun.
- Paket dasar serba bisa = preset "Kelas Lengkap" milik pemakai. Paket
  mengizinkan lebar, TEMPLATE yang menyaring spec yang dikirim ke AI
  (hanya modul yang dipakai bagian-bagian template) — prompt tetap ramping.
- Template bawaan (dibuat_oleh NULL) tidak bisa diubah; fork dulu.
"""

from typing import Optional

from sqlalchemy.orm import Session

from .models import ParserPack, PedagogyTemplate, User
from .paket import ensure_preset_packs, pack_module_rows, spec_text_for_selection
from .tcml.registry import MODULES

PERAN_BAGIAN = {
    "pembuka", "konsep", "contoh", "kasus", "diskusi",
    "cek", "latihan", "proyek", "ringkasan", "bebas",
}
STATUS_BAGIAN = {"wajib", "opsional", "pilihan"}


def _b(peran, label, status, modul, catatan=""):
    return {
        "peran": peran, "label": label, "status": status,
        "modul": modul, "catatan": catatan,
    }


PRESET_TEMPLATES: list[dict] = [
    {
        "nama": "Konsep Bertahap",
        "deskripsi": "Alur teori yang runtut: pembuka, konsep inti, contoh, cek pemahaman, latihan, ringkasan. Cocok untuk materi konseptual.",
        "bagian": [
            _b("pembuka", "Pembuka", "wajib", ["inti-materi"],
               "Buka dengan SATU pemicu: pertanyaan pemicu, kasus sangat singkat, atau miskonsepsi umum — pilih yang paling cocok dengan topik, jangan ketiganya."),
            _b("konsep", "Konsep Inti", "wajib", ["inti-materi", "tabel-data", "formula-kode"],
               "Jelaskan konsep per sub-bahasan dengan heading; definisi dulu, baru uraian. Gunakan tabel/formula hanya bila memang membantu."),
            _b("contoh", "Contoh Terapan", "wajib", ["inti-materi"],
               "Satu contoh konkret yang dikerjakan langkah demi langkah, dekat dengan kehidupan siswa."),
            _b("cek", "Cek Pemahaman", "opsional", ["cek-pemahaman"],
               "Soal sisipan menempel ke konsep yang baru dijelaskan."),
            _b("latihan", "Latihan", "opsional", ["latihan"],
               "Latihan singkat agar siswa mencoba sendiri."),
            _b("ringkasan", "Ringkasan", "wajib", ["inti-materi"],
               "Tutup dengan ringkasan poin kunci (SUMMARY) dan satu kalimat jembatan ke pertemuan berikutnya bila konteksnya ada."),
        ],
    },
    {
        "nama": "Berbasis Kasus",
        "deskripsi": "Mulai dari kasus nyata, konsep dibedah dari kasus itu, lalu diskusi dan kasus lanjutan. Cocok untuk materi terapan & sosial.",
        "bagian": [
            _b("kasus", "Kasus Pembuka", "wajib", ["inti-materi"],
               "Sajikan satu studi kasus nyata/semi-nyata yang utuh di awal, dengan tokoh dan situasi yang jelas. Kasus ini menjadi jangkar seluruh materi."),
            _b("konsep", "Bedah Konsep", "wajib", ["inti-materi", "tabel-data"],
               "Jelaskan konsep-konsep yang muncul di kasus, selalu merujuk kembali ke kasusnya."),
            _b("diskusi", "Pertanyaan Diskusi", "wajib", ["inti-materi"],
               "2-3 pertanyaan diskusi terbuka yang menggali kasus dari sudut pandang berbeda; bukan pertanyaan hafalan."),
            _b("kasus", "Kasus Lanjutan", "opsional", ["inti-materi", "latihan"],
               "Variasi kasus pertama (situasi diubah) untuk dianalisis siswa dengan konsep yang sama."),
            _b("cek", "Cek Pemahaman", "opsional", ["cek-pemahaman"], ""),
            _b("ringkasan", "Ringkasan", "wajib", ["inti-materi"],
               "Ringkasan yang mengikat konsep kembali ke kasus pembuka."),
        ],
    },
    {
        "nama": "Praktik Langsung",
        "deskripsi": "Untuk keterampilan: tujuan, demo langkah demi langkah, praktik terbimbing, proyek mini. Cocok untuk komputer, bahasa, dan keterampilan teknis.",
        "bagian": [
            _b("pembuka", "Tujuan & Gambaran Hasil", "wajib", ["inti-materi"],
               "Sampaikan hasil akhir yang akan bisa dibuat/dilakukan siswa di pertemuan ini."),
            _b("konsep", "Demo Langkah demi Langkah", "wajib", ["inti-materi", "formula-kode"],
               "Langkah bernomor yang bisa diikuti persis; tiap langkah singkat, sertakan hasil antara yang seharusnya terlihat."),
            _b("latihan", "Praktik Terbimbing", "wajib", ["latihan"],
               "Tugas praktik mengikuti demo dengan variasi kecil, plus titik cek mandiri di tengahnya."),
            _b("cek", "Cek Pemahaman", "opsional", ["cek-pemahaman"],
               "Cek konsep kunci di balik langkah-langkah praktik (bukan hafalan langkah)."),
            _b("proyek", "Proyek Mini", "opsional", ["proyek"],
               "Proyek kecil mandiri yang menggabungkan semua langkah pertemuan ini."),
            _b("ringkasan", "Ringkasan & Kesalahan Umum", "opsional", ["inti-materi"],
               "Ringkasan langkah kunci + kesalahan yang paling sering terjadi dan cara menghindarinya."),
        ],
    },
    {
        "nama": "Eksplorasi Masalah",
        "deskripsi": "Mulai dari masalah/miskonsepsi, siswa diajak mengeksplorasi sebelum konsep diformalkan. Cocok untuk sains & matematika.",
        "bagian": [
            _b("pembuka", "Masalah Pemicu", "wajib", ["inti-materi"],
               "Sajikan masalah atau fenomena yang jawabannya tidak intuitif; jangan beri jawabannya dulu."),
            _b("konsep", "Eksplorasi Konsep", "wajib", ["inti-materi", "formula-kode", "tabel-data"],
               "Bangun konsep sebagai jawaban atas masalah pemicu, langkah demi langkah."),
            _b("contoh", "Contoh Pembanding", "opsional", ["inti-materi"],
               "Satu contoh yang menegaskan beda cara berpikir lama (intuisi awal) vs konsep yang benar."),
            _b("diskusi", "Diskusi", "wajib", ["inti-materi"],
               "Pertanyaan diskusi yang menguji apakah siswa bisa menerapkan konsep ke situasi baru."),
            _b("cek", "Cek Pemahaman", "opsional", ["cek-pemahaman"], ""),
            _b("latihan", "Latihan", "opsional", ["latihan"], ""),
            _b("ringkasan", "Ringkasan", "wajib", ["inti-materi"],
               "Ringkasan yang secara eksplisit menjawab masalah pemicu di awal."),
        ],
    },
]


def validate_bagian(bagian) -> list[dict]:
    """Normalisasi + validasi daftar bagian template. ValueError berpesan
    ramah bila tidak sah."""
    if bagian is None:
        return []
    if not isinstance(bagian, list) or len(bagian) > 20:
        raise ValueError("Daftar bagian template tidak sah (maksimal 20 bagian).")
    hasil = []
    for b in bagian:
        if not isinstance(b, dict):
            raise ValueError("Setiap bagian template harus berupa objek.")
        peran = str(b.get("peran") or "bebas")
        if peran not in PERAN_BAGIAN:
            raise ValueError(f"Peran bagian tidak dikenal: {peran}.")
        status = str(b.get("status") or "wajib")
        if status not in STATUS_BAGIAN:
            raise ValueError(f"Status bagian tidak dikenal: {status}.")
        modul = [str(s) for s in (b.get("modul") or []) if str(s) in MODULES]
        hasil.append({
            "peran": peran,
            "label": str(b.get("label") or peran.capitalize())[:80],
            "status": status,
            "modul": modul,
            "catatan": str(b.get("catatan") or "")[:600],
        })
    return hasil


def ensure_preset_templates(db: Session) -> None:
    """Buat template bawaan sistem (dibuat_oleh NULL) bila belum ada."""
    existing = {
        t.nama
        for t in db.query(PedagogyTemplate)
        .filter(PedagogyTemplate.dibuat_oleh.is_(None))
        .all()
    }
    for preset in PRESET_TEMPLATES:
        if preset["nama"] not in existing:
            db.add(PedagogyTemplate(
                nama=preset["nama"],
                deskripsi=preset["deskripsi"],
                dibuat_oleh=None,
                visibilitas="shared",
                paket_dasar=True,
                pack_id=None,
                bagian=validate_bagian(preset["bagian"]),
            ))
    db.commit()


def can_access_template(user: User, t: PedagogyTemplate) -> bool:
    if t.dibuat_oleh is None:  # preset sistem
        return True
    if user.role == "admin" or t.dibuat_oleh == user.id:
        return True
    return t.visibilitas == "shared"


def template_out(db: Session, t: PedagogyTemplate, viewer: User) -> dict:
    owner = db.get(User, t.dibuat_oleh) if t.dibuat_oleh else None
    return {
        "id": t.id,
        "nama": t.nama,
        "deskripsi": t.deskripsi,
        "dibuat_oleh": t.dibuat_oleh,
        "pemilik": (owner.nama_lengkap or owner.username) if owner else "Sistem",
        "preset": t.dibuat_oleh is None,
        "visibilitas": t.visibilitas,
        "pack_id": t.pack_id,
        "paket_dasar": t.paket_dasar,
        "bagian": t.bagian or [],
        "milik_saya": t.dibuat_oleh == viewer.id,
        "bisa_ubah": t.dibuat_oleh is not None and t.dibuat_oleh == viewer.id,
    }


def resolve_pack(db: Session, user: User, t: PedagogyTemplate) -> ParserPack:
    """Paket efektif sebuah template untuk pemakai tertentu: paket rujukan
    eksplisit bila ada & bisa diakses; selain itu paket dasar serba bisa
    (preset 'Kelas Lengkap' milik pemakai, dibuat bila belum ada)."""
    if not t.paket_dasar and t.pack_id:
        pack = db.get(ParserPack, t.pack_id)
        if pack is not None:
            from .paket import can_access_pack

            if can_access_pack(db, user, pack):
                return pack
    ensure_preset_packs(db, user)
    pack = (
        db.query(ParserPack)
        .filter(ParserPack.dibuat_oleh == user.id, ParserPack.nama == "Kelas Lengkap")
        .first()
    )
    if pack is None:  # sangat defensif — ensure seharusnya membuatnya
        pack = db.query(ParserPack).filter(ParserPack.dibuat_oleh == user.id).first()
    return pack


def narrowed_selection(
    db: Session, t: PedagogyTemplate, pack: ParserPack
) -> tuple[list[str], Optional[dict]]:
    """Irisan pilihan modul/tag paket dengan modul yang dipakai template —
    inilah penyaringan spec oleh template (paket boleh lebar, spec yang
    dikirim hanya yang relevan dengan alur). Template tanpa modul pada
    bagiannya tidak menyaring apa pun."""
    pack_slugs = [m.slug for m in pack_module_rows(db, pack)]
    modul_template: list[str] = []
    for b in t.bagian or []:
        for slug in b.get("modul") or []:
            if slug not in modul_template:
                modul_template.append(slug)
    if modul_template:
        slugs = [s for s in pack_slugs if s in modul_template]
        if not slugs:
            slugs = pack_slugs
    else:
        slugs = pack_slugs
    tag_pilihan = None
    if pack.tag_pilihan:
        tag_pilihan = {
            slug: list(pack.tag_pilihan.get(slug, []))
            for slug in slugs
            if pack.tag_pilihan.get(slug)
        } or None
    return slugs, tag_pilihan


def spec_for_template(db: Session, t: PedagogyTemplate, pack: ParserPack) -> str:
    slugs, tag_pilihan = narrowed_selection(db, t, pack)
    return spec_text_for_selection(db, slugs, tag_pilihan)


def instruksi_urutan(t: PedagogyTemplate) -> str:
    """Blok instruksi alur untuk prompt generate: urutan bagian + status +
    catatan gaya per bagian."""
    if not t.bagian:
        return ""
    lines = [
        f"Ikuti ALUR MENGAJAR '{t.nama}' berikut secara berurutan "
        "(bagian berstatus opsional boleh dibuat bila relevan dengan topik; "
        "bagian berstatus pilihan = ikuti catatan gayanya):"
    ]
    for i, b in enumerate(t.bagian, start=1):
        catatan = f" — {b['catatan']}" if b.get("catatan") else ""
        lines.append(f"{i}. [{b['peran']}] {b['label']} ({b['status']}){catatan}")
    return "\n".join(lines)
