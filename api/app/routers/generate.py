"""Router Generate AI (Fase 5).

Alur: guru memilih paket parser + Pengaturan AI + brief -> prompt dirakit
HANYA dari modul paket -> AI menjawab (boleh bundle multi-dokumen) ->
keluaran dipecah per root block -> tiap dokumen divalidasi 2 lapis ->
tersimpan sebagai ContentDraft. Draf TIDAK pernah terbit otomatis: guru
meninjau, memperbaiki (manual atau self-repair AI, maks 2x), lalu menyimpan
ke bank atau menerbitkan ke pertemuan.
"""

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import get_meeting, get_subject, require_subject_manage
from ..ai_akses import resolusi_setting
from ..ai_client import ProviderError, chat_completion
from ..db import get_db
from ..deps import get_current_user, require_csrf, write_audit
from ..models import (
    AiSetting,
    AuditLog,
    ContentDraft,
    GenerationJob,
    Material,
    ParserPack,
    PedagogyTemplate,
    Quiz,
    SavedMaterial,
    SavedQuiz,
    User,
)
from ..paket import (
    build_system_prompt,
    can_access_pack,
    pack_module_rows,
    roots_for_slugs,
    spec_text_for_selection,
    split_documents,
    validate_bundle_document,
    validate_document,
)
from ..pedagogi import (
    can_access_template,
    instruksi_urutan,
    narrowed_selection,
    resolve_pack,
)
from ..tcml.quiz import normalisasi_format_kuis, parse_quiz_v2
from .materials import _parse_or_400 as _material_parse_or_400
from .quizzes import _create_questions, _notify_quiz_baru
from .quizzes import _parse_or_400 as _quiz_parse_or_400

router = APIRouter(prefix="/api/v1/generate", tags=["generate"])
staff_roles = ("guru", "admin")
MAX_REPAIR = 2


def _staff(user: User = Depends(get_current_user)) -> User:
    if user.role not in staff_roles:
        raise HTTPException(status_code=403, detail="Fitur ini hanya untuk guru/admin.")
    return user


def draft_out(d: ContentDraft) -> dict:
    return {
        "id": d.id,
        "generation_job_id": d.generation_job_id,
        "jenis": d.jenis,
        "tipe_quiz": d.tipe_quiz,
        "judul": d.judul,
        "teks_mentah": d.teks_mentah,
        "is_valid": d.is_valid,
        "errors": d.errors or [],
        "status": d.status,
        "published_id": d.published_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _own_draft(db: Session, user: User, draft_id: int) -> ContentDraft:
    d = db.get(ContentDraft, draft_id)
    if d is None or d.user_id != user.id:
        raise HTTPException(status_code=404, detail="Draf tidak ditemukan.")
    return d


JENIS_DOKUMEN_VALID = ("materi", "tugas", "kuis", "ujian")


def _jenis_dokumen_draf(db: Session, d: ContentDraft) -> str:
    """Audit #8: jenis dokumen pilihan guru tersimpan di brief job generate;
    dulu publish/save-bank meng-hardcode 'materi' sehingga draf Ujian/Tugas
    terbit sebagai Materi Biasa."""
    if d.jenis != "dokumen":
        return "materi"
    job = db.get(GenerationJob, d.generation_job_id) if d.generation_job_id else None
    nilai = ((job.brief or {}).get("jenis_dokumen") if job else None) or "materi"
    nilai = str(nilai).strip().lower()
    return nilai if nilai in JENIS_DOKUMEN_VALID else "materi"


def _pengaturan_generate(jenis_dok: str):
    """Preset pengaturan kuis untuk terbit dari Generate (semua opsional —
    preset hanya untuk Ujian: acak soal & opsi menyala, meniru editor)."""
    from .documents import QuizSettingsIn

    if jenis_dok == "ujian":
        return QuizSettingsIn(acak_soal=True, acak_opsi=True)
    return QuizSettingsIn()


def _tolak_sudah_final(d: ContentDraft) -> None:
    """Audit #8: publish/save-bank tidak boleh mengulang draf yang sudah
    final — klik ganda dulu membuat dokumen/kuis duplikat."""
    if d.status == "published":
        raise HTTPException(
            status_code=400,
            detail="Draf ini sudah diterbitkan/disimpan ke bank sebelumnya — duplikat dicegah. Buka hasil terbitannya untuk mengedit.",
        )


def _resolve_setting(db: Session, user: User, setting_id: Optional[int]) -> AiSetting:
    # Resolusi terpusat di ai_akses: milik sendiri didahulukan; pengaturan
    # yang DIBAGIKAN admin (semua/whitelist/blacklist) menjadi cadangan
    # dan bisa dipilih eksplisit via ai_setting_id.
    return resolusi_setting(db, user, setting_id)


KEPADATAN_CEK = {"jarang": 2, "sedang": 4, "padat": 6}


def _materi_like(kind: str, brief: dict) -> bool:
    """Generate yang hasilnya materi/tugas (bukan kuis betulan) — untuk
    jenis ini jumlah soal bersifat kepadatan, bukan kuota."""
    if kind == "materi":
        return True
    if kind == "dokumen":
        return (brief.get("jenis_dokumen") or "materi") in ("materi", "tugas")
    return False


def _brief_to_user_prompt(kind: str, brief: dict, slugs: list[str] | None = None, boleh_materi: bool = True, dua_tahap: bool = False) -> str:
    topik = (brief.get("topik") or "").strip()
    instruksi = (brief.get("instruksi") or "").strip()
    punya_cek = bool(slugs and "cek-pemahaman" in slugs)
    if kind == "materi":
        target = "satu dokumen materi belajar (root [MATERIAL], boleh juga [EXERCISE]/[PROJECT] bila diminta)"
    elif kind == "kuis_pg":
        target = "satu dokumen kuis pilihan ganda (root [QUIZ], [TYPE]pilihan_ganda[/TYPE])"
    elif kind == "dokumen":
        # Bentuk keluaran mengikuti JENIS dokumen yang dipilih guru:
        # materi biasa = campuran bacaan + soal sisipan; kuis/ujian =
        # kuis betulan berprolog; tugas = dokumen praktik/proyek.
        jenis_dok = (brief.get("jenis_dokumen") or "materi").strip()
        if jenis_dok == "tugas":
            target = (
                "satu DOKUMEN TUGAS: dokumen praktik/proyek (root [EXERCISE] atau [PROJECT]) "
                "berisi penjelasan singkat, daftar tugas/langkah yang harus dikerjakan siswa, "
                "dan hasil yang diharapkan"
            )
            if punya_cek:
                target += "; selipkan 1-2 soal [CEK] Cek Pemahaman bila ada konsep yang perlu dicek sebelum praktik"
        elif jenis_dok in ("kuis", "ujian"):
            nama = "UJIAN" if jenis_dok == "ujian" else "KUIS"
            # Audit #20: bacaan pendamping hanya ditawarkan bila paket memang
            # mengizinkan akar materi — dulu selalu ditawarkan sehingga draf
            # bisa gugur oleh validasi paketnya sendiri.
            pendamping = (
                "; boleh didahului satu root [MATERIAL] bacaan "
                "pendamping singkat bila materinya memang perlu dibaca dulu"
                if boleh_materi
                else "; dokumen HANYA berisi root [QUIZ] (paket ini tidak mengizinkan akar materi pendamping)"
            )
            target = (
                f"satu DOKUMEN {nama} betulan: root [QUIZ] yang diawali blok pengantar "
                "(paragraf sambutan/konteks dan [NOTE] petunjuk pengerjaan"
                + (", [WARNING] aturan ujian" if jenis_dok == "ujian" else "")
                + ") lalu soal-soalnya"
                + pendamping
            )
            if jenis_dok == "kuis":
                target += ". [HINT] boleh diselipkan di antara soal sebagai petunjuk"
            else:
                target += ". JANGAN menyelipkan [HINT] di antara soal (ini ujian)"
        else:
            target = (
                "satu DOKUMEN MATERI campuran: bacaan (root [MATERIAL], boleh diselingi "
                "[EXERCISE] bila topiknya praktik) yang mengalir utuh"
            )
            if punya_cek:
                target += (
                    ", dengan soal sisipan [CEK] Cek Pemahaman diselipkan tepat setelah "
                    "bagian penting yang ingin dicek pemahamannya (1 soal per bagian, "
                    "jangan menumpuk di akhir)"
                )
    else:
        target = "satu dokumen kuis esai (root [QUIZ], [TYPE]essay[/TYPE])"
    lines = [f"Buatkan {target} tentang: {topik}."]
    if brief.get("jenjang"):
        lines.append(f"Jenjang/kelas: {brief['jenjang']}.")
    kepadatan = str(brief.get("kepadatan_cek") or "").strip().lower()
    pakai_kepadatan = _materi_like(kind, brief) and kepadatan in KEPADATAN_CEK and punya_cek
    if kind in ("kuis_pg", "kuis_esai", "dokumen") and brief.get("jumlah_soal") and not pakai_kepadatan:
        lines.append(f"Jumlah soal: {brief['jumlah_soal']}.")
    if pakai_kepadatan and not dua_tahap:
        # Tanpa dua tahap, kepadatan disampaikan sebagai kisaran lunak —
        # BUKAN kuota: akar masalah lama adalah angka pasti yang dikejar
        # model sampai soal ditabur ke paragraf yang tidak nyambung.
        lines.append(
            f"Soal sisipan [CEK]: kepadatan {kepadatan} (sekitar {KEPADATAN_CEK[kepadatan]} soal, "
            "MAKSIMAL 1 per bagian, hanya setelah konsepnya selesai dijelaskan dan hanya untuk "
            "konsep yang benar-benar penting — lebih baik kurang daripada memaksakan jumlah)."
        )
    if brief.get("aktivitas"):
        dipilih = [str(a) for a in brief["aktivitas"] if str(a).strip()]
        if dipilih:
            lines.append(
                "Komposisi aktivitas yang WAJIB hadir dalam materi (di luar bacaan inti): "
                + ", ".join(dipilih) + "."
            )
    if instruksi:
        lines.append(f"Instruksi tambahan: {instruksi}")
    return "\n".join(lines)


# ------------------------------------------------------------ dua tahap
_CEK_RE = re.compile(r"\[CEK\][\s\S]*?\[/CEK\]")
_ROOT_MATERIAL_RE = re.compile(r"\[MATERIAL\]([\s\S]*?)\[/MATERIAL\]")
_HEADING_SPLIT_RE = re.compile(r"(\[HEADING\][\s\S]*?\[/HEADING\])")
_UNIT_TAHAP2_RE = re.compile(r"\[TARGET\]([\s\S]*?)\[/TARGET\]\s*(\[CEK\][\s\S]*?\[/CEK\])")


def _strip_cek(teks: str) -> str:
    """Buang blok [CEK] dari keluaran tahap 1 (tahap 2 menulisnya ulang
    berdasarkan materi jadi, agar soal menempel ke isi)."""
    return _CEK_RE.sub("", teks)


def _bagian_materi(teks: str):
    """Pecah isi root [MATERIAL] menjadi segmen per [HEADING].
    Mengembalikan (match_root, segmen) — segmen[0] adalah pembuka sebelum
    heading pertama (heading=None). None bila tak ada root materi."""
    m = _ROOT_MATERIAL_RE.search(teks)
    if not m:
        return None
    parts = _HEADING_SPLIT_RE.split(m.group(1))
    segmen = [{"heading": None, "teks": parts[0], "cek": False}]
    i = 1
    while i < len(parts):
        heading = re.sub(r"\[/?HEADING\]", "", parts[i]).strip()
        isi = parts[i + 1] if i + 1 < len(parts) else ""
        segmen.append({"heading": heading, "teks": parts[i] + isi, "cek": False})
        i += 2
    return m, segmen


def _norm_heading(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _sisipkan_cek(teks: str, units: list[tuple[str, str]], maks: int) -> str:
    """Sisipkan blok [CEK] (dari tahap 2) di akhir bagian [HEADING]
    targetnya; target tak ketemu -> bagian terpanjang yang belum berisi
    CEK. Maksimal 1 CEK per bagian, total dibatasi `maks`."""
    hasil_bagian = _bagian_materi(teks)
    if not hasil_bagian:
        return teks
    m, segmen = hasil_bagian
    terpakai = 0
    for target, blok in units:
        if terpakai >= maks:
            break
        idx = None
        nt = _norm_heading(target)
        for j, seg in enumerate(segmen):
            if seg["heading"] is not None and not seg["cek"] and _norm_heading(seg["heading"]) == nt:
                idx = j
                break
        if idx is None:
            kandidat = [j for j, seg in enumerate(segmen) if j > 0 and not seg["cek"]]
            if not kandidat and len(segmen) > 1:
                break
            if not kandidat:
                kandidat = [0] if not segmen[0]["cek"] else []
            if not kandidat:
                break
            idx = max(kandidat, key=lambda j: len(segmen[j]["teks"]))
        segmen[idx]["teks"] = segmen[idx]["teks"].rstrip() + "\n" + blok.strip() + "\n"
        segmen[idx]["cek"] = True
        terpakai += 1
    if not terpakai:
        return teks
    isi_baru = "".join(seg["teks"] for seg in segmen)
    return teks[: m.start(1)] + isi_baru + teks[m.end(1):]


def _prompt_tahap2(teks_materi: str, target_jumlah: int) -> tuple[str, str]:
    """Prompt tahap 2: AI menerima materi JADI dan menulis soal sisipan
    yang menempel per bagian. Keluaran wajib berformat [TARGET]+[CEK]."""
    hasil_bagian = _bagian_materi(teks_materi)
    headings = []
    if hasil_bagian:
        headings = [s["heading"] for s in hasil_bagian[1] if s["heading"]]
    daftar = "\n".join(f"- {h}" for h in headings) or "- (materi tanpa sub-bagian; targetkan heading kosong)"
    system = (
        "Kamu menulis soal sisipan Cek Pemahaman [CEK] untuk materi yang SUDAH JADI. "
        "Soal harus menempel persis ke isi bagian yang ditargetkan — uji pemahaman konsep "
        "bagian itu, bukan hafalan umum. Keluarkan HANYA unit-unit berikut, tanpa teks lain:\n"
        "[TARGET]teks heading bagian persis seperti di materi[/TARGET]\n"
        "[CEK]...satu blok soal sisipan...[/CEK]\n"
        "Maksimal 1 unit per bagian. Variasikan bentuk: pilihan ganda dan esai singkat."
    )
    user = (
        f"Tulis {target_jumlah} soal sisipan untuk materi berikut.\n"
        f"Bagian-bagian yang tersedia sebagai target:\n{daftar}\n\n"
        f"MATERI:\n{teks_materi}"
    )
    return system, user


_PENANDA_STRUKTUR = {
    "cek": ("[CEK]", "soal sisipan [CEK]"),
    "latihan": ("[EXERCISE]", "blok [EXERCISE]"),
    "proyek": ("[PROJECT]", "blok [PROJECT]"),
    "ringkasan": ("[SUMMARY]", "blok [SUMMARY]"),
    "contoh": ("[EXAMPLE]", "blok [EXAMPLE]"),
}


def _cek_struktur(template: PedagogyTemplate, teks: str) -> list[str]:
    """Cek struktur lunak terhadap template: bagian WAJIB yang penandanya
    tidak ditemukan menjadi PERINGATAN (bukan penolakan) pada hasil
    generate — validasi berubah dari polisi format jadi umpan balik."""
    peringatan = []
    for b in template.bagian or []:
        if b.get("status") != "wajib":
            continue
        penanda = _PENANDA_STRUKTUR.get(b.get("peran"))
        if penanda and penanda[0] not in teks:
            peringatan.append(
                f"Alur '{template.nama}': bagian wajib '{b['label']}' tampaknya tidak dibuat AI "
                f"(tidak ditemukan {penanda[1]}). Periksa drafnya — Anda bisa menambahkannya lewat editor."
            )
    return peringatan


def _bangun_konteks(db: Session, subject, meeting, kind: str, brief: dict) -> str:
    """Konteks kesinambungan untuk generate dari dalam pertemuan (desain
    3-AI): info kelas + rencana pertemuan ini + ringkasan AKTUAL pertemuan
    sebelumnya. Untuk kuis, yang paling relevan adalah isi aktual
    pertemuan ini sendiri (yang benar-benar diajarkan)."""
    from ..models import Meeting
    from ..ringkasan import segarkan_ringkasan

    baris = ["KONTEKS KELAS (untuk kesinambungan antarpertemuan):"]
    info = f"Kelas: {subject.nama}"
    if subject.jenjang:
        info += f" — jenjang {subject.jenjang}"
    if subject.target_siswa:
        info += f"; target siswa: {subject.target_siswa}"
    if subject.tujuan_akhir:
        info += f"; tujuan akhir: {subject.tujuan_akhir}"
    baris.append(info)
    rencana = meeting.rencana or {}
    if rencana:
        potongan = f"Rencana pertemuan ini ('{meeting.judul}')"
        if rencana.get("tujuan"):
            potongan += f" — tujuan: {rencana['tujuan']}"
        if rencana.get("konsep"):
            potongan += "; konsep kunci: " + ", ".join(rencana["konsep"])
        if rencana.get("aktivitas"):
            potongan += "; aktivitas: " + ", ".join(rencana["aktivitas"])
        baris.append(potongan + ".")
    if not _materi_like(kind, brief):
        ringkasan_ini = segarkan_ringkasan(db, meeting)
        if ringkasan_ini:
            baris.append(
                "Isi aktual pertemuan ini (buat soal HANYA dari yang benar-benar diajarkan ini):\n"
                + ringkasan_ini
            )
    sebelumnya = (
        db.query(Meeting)
        .filter(Meeting.subject_id == subject.id, Meeting.urutan < meeting.urutan)
        .order_by(Meeting.urutan)
        .all()
    )
    ringkasan_lalu = []
    for m in sebelumnya[-6:]:
        teks = segarkan_ringkasan(db, m)
        if teks:
            ringkasan_lalu.append(teks)
    if ringkasan_lalu:
        baris.append(
            "Pertemuan sebelumnya (aktual, sudah diajarkan — JANGAN jelaskan ulang konsepnya, "
            "rujuk seperlunya dan pakai istilah yang sama):\n" + "\n".join(ringkasan_lalu)[:3000]
        )
    return "\n".join(baris)


class GenerateIn(BaseModel):
    kind: str = Field(pattern="^(materi|kuis_pg|kuis_esai|dokumen)$")
    pack_id: int
    ai_setting_id: Optional[int] = None
    template_id: Optional[int] = None
    brief: dict = Field(default_factory=dict)


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def generate(body: GenerateIn, user: User = Depends(_staff), db: Session = Depends(get_db)):
    if not (body.brief.get("topik") or "").strip():
        raise HTTPException(status_code=400, detail="Brief wajib berisi topik.")
    # Konteks pertemuan (bila brief membawa subject_id+meeting_id —
    # generate diluncurkan dari dalam kelas): bangun blok kesinambungan
    # dan tebak template dari rencana pertemuan / default kelas.
    konteks_blok = ""
    template_id_efektif = body.template_id
    subj_id, meet_id = body.brief.get("subject_id"), body.brief.get("meeting_id")
    if subj_id and meet_id:
        try:
            subject = get_subject(db, int(subj_id))
            meeting = get_meeting(db, int(meet_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Konteks pertemuan tidak sah.")
        require_subject_manage(db, user, subject)
        if meeting.subject_id != subject.id:
            raise HTTPException(status_code=400, detail="Pertemuan tidak termasuk kelas ini.")
        konteks_blok = _bangun_konteks(db, subject, meeting, body.kind, body.brief)
        if not template_id_efektif:
            from ..pedagogi import ensure_preset_templates

            ensure_preset_templates(db)
            nama_alur = (meeting.rencana or {}).get("alur")
            candidates = db.query(PedagogyTemplate).all()
            if nama_alur:
                for t in candidates:
                    if t.nama == nama_alur and can_access_template(user, t):
                        template_id_efektif = t.id
                        break
            if not template_id_efektif and subject.template_default_id:
                template_id_efektif = subject.template_default_id

    # Template pedagogi (bila dipilih): paket efektif berasal dari
    # template (rujukannya / paket dasar), dan spec DISARING oleh modul
    # yang dipakai bagian-bagian template.
    template: Optional[PedagogyTemplate] = None
    if template_id_efektif:
        template = db.get(PedagogyTemplate, template_id_efektif)
        if template is None or not can_access_template(user, template):
            raise HTTPException(status_code=404, detail="Template tidak ditemukan.")
        pack = resolve_pack(db, user, template)
        if pack is None:
            raise HTTPException(status_code=400, detail="Template ini tidak memiliki paket yang bisa dipakai.")
    else:
        pack = db.get(ParserPack, body.pack_id)
        if pack is None or not can_access_pack(db, user, pack):
            raise HTTPException(status_code=404, detail="Paket tidak ditemukan.")
    setting = _resolve_setting(db, user, body.ai_setting_id)

    if template is not None:
        slugs, tag_pilihan_sempit = narrowed_selection(db, template, pack)
        spec_sempit = spec_text_for_selection(db, slugs, tag_pilihan_sempit)
        system_prompt = build_system_prompt(db, pack, body.kind, spec_override=spec_sempit)
    else:
        slugs = [m.slug for m in pack_module_rows(db, pack)]
        system_prompt = build_system_prompt(db, pack, body.kind)
    roots_pack = pack.allowed_roots or roots_for_slugs(slugs)
    boleh_materi = any(r in roots_pack for r in ("MATERIAL", "EXERCISE", "PROJECT"))

    # Dua tahap aktif bila: hasil materi-like, modul cek tersedia, dan
    # (template punya bagian cek ATAU guru mengatur kepadatan eksplisit).
    kepadatan = str(body.brief.get("kepadatan_cek") or "").strip().lower()
    template_punya_cek = bool(
        template and any(b.get("peran") == "cek" for b in (template.bagian or []))
    )
    dua_tahap = bool(
        _materi_like(body.kind, body.brief)
        and "cek-pemahaman" in slugs
        and (template_punya_cek or kepadatan in KEPADATAN_CEK)
    )
    user_prompt = _brief_to_user_prompt(
        body.kind, body.brief, slugs, boleh_materi=boleh_materi, dua_tahap=dua_tahap
    )
    if konteks_blok:
        user_prompt += "\n\n" + konteks_blok
    if template is not None and _materi_like(body.kind, body.brief):
        urutan = instruksi_urutan(template)
        if urutan:
            user_prompt += "\n\n" + urutan
    if dua_tahap:
        user_prompt += (
            "\n\nCATATAN TAHAP PENULISAN: pada tahap ini JANGAN menulis soal [CEK] apa pun — "
            "tulis isi materinya saja selengkap dan sestruktur mungkin. Soal sisipan ditambahkan "
            "pada tahap berikutnya berdasarkan materi yang sudah jadi."
        )
    job = GenerationJob(
        user_id=user.id,
        pack_id=pack.id,
        ai_setting_id=setting.id,
        brief={**body.brief, "kind": body.kind, "template_id": template_id_efektif},
        prompt_final=system_prompt + "\n\n---\n\n" + user_prompt,
        status="running",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        raw = chat_completion(
            setting,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except ProviderError as e:
        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(e))

    peringatan: list[str] = []
    if dua_tahap:
        # TAHAP 2: soal sisipan ditulis BERDASARKAN materi jadi, lalu
        # disisipkan di akhir bagian targetnya. Kegagalan tahap 2 tidak
        # menggagalkan generate — materi tetap menjadi draf (tanpa soal
        # sisipan baru) dan guru diberi tahu lewat peringatan.
        mentah = _strip_cek(raw)
        target = KEPADATAN_CEK.get(kepadatan, KEPADATAN_CEK["sedang"])
        try:
            spec_cek = spec_text_for_selection(
                db,
                ["cek-pemahaman"],
                {"cek-pemahaman": list(pack.tag_pilihan.get("cek-pemahaman", []))}
                if pack.tag_pilihan and pack.tag_pilihan.get("cek-pemahaman")
                else None,
            )
            sys2, usr2 = _prompt_tahap2(mentah, target)
            raw2 = chat_completion(
                setting,
                [
                    {"role": "system", "content": sys2 + "\n\n" + spec_cek},
                    {"role": "user", "content": usr2},
                ],
            )
            units = []
            from ..tcml.cek import extract_ceks

            for target_heading, blok in _UNIT_TAHAP2_RE.findall(raw2):
                _, errs = extract_ceks(blok)
                if not errs:
                    units.append((target_heading, blok))
            if units:
                raw = _sisipkan_cek(mentah, units, target)
            else:
                raw = mentah
                peringatan.append(
                    "Tahap soal sisipan tidak menghasilkan soal yang sah — draf berisi materi saja. "
                    "Anda bisa menambahkan Cek Pemahaman lewat editor."
                )
        except ProviderError:
            raw = mentah
            peringatan.append(
                "Tahap soal sisipan gagal dihubungi — draf berisi materi saja, tanpa soal sisipan baru."
            )
    if template is not None:
        peringatan.extend(_cek_struktur(template, raw))

    job.raw_output = raw
    job.status = "done"
    job.finished_at = datetime.now(timezone.utc)

    drafts: list[ContentDraft] = []
    if body.kind == "dokumen":
        # Dokumen terpadu: SELURUH keluaran adalah SATU dokumen gabungan —
        # jangan dipecah per root seperti bundle biasa.
        teks = "\n".join(
            ln for ln in raw.splitlines() if not ln.strip().startswith("```")
        ).strip()
        teks = normalisasi_format_kuis(teks)
        v = validate_bundle_document(db, pack, teks)
        d = ContentDraft(
            generation_job_id=job.id,
            user_id=user.id,
            jenis="dokumen",
            tipe_quiz=None,
            judul=v["judul"],
            teks_mentah=teks,
            is_valid=v["valid"],
            errors=v["errors"],
            status="draft",
        )
        db.add(d)
        drafts.append(d)
    else:
        for teks in split_documents(raw):
            teks = normalisasi_format_kuis(teks)
            v = validate_document(db, pack, body.kind, teks)
            d = ContentDraft(
                generation_job_id=job.id,
                user_id=user.id,
                jenis=v["jenis"] or ("quiz" if body.kind != "materi" else "material"),
                tipe_quiz=v["tipe_quiz"],
                judul=v["judul"],
                teks_mentah=teks,
                is_valid=v["valid"],
                errors=v["errors"],
                status="draft",
            )
            db.add(d)
            drafts.append(d)
    db.commit()
    for d in drafts:
        db.refresh(d)
    if not drafts:
        raise HTTPException(
            status_code=502,
            detail="AI tidak menghasilkan dokumen TCML apa pun. Coba perjelas topik/instruksi, atau periksa model yang dipakai.",
        )
    return {
        "job_id": job.id,
        "model": setting.model,
        "pack_id": pack.id,
        "template_id": template_id_efektif,
        "dua_tahap": dua_tahap,
        "peringatan_struktur": peringatan,
        "drafts": [draft_out(d) for d in drafts],
    }


class ImportIn(BaseModel):
    kind: str = Field(pattern="^(materi|kuis_pg|kuis_esai|dokumen)$")
    pack_id: int
    teks: str = Field(min_length=1)


@router.post("/import", status_code=201, dependencies=[Depends(require_csrf)])
def import_external(body: ImportIn, user: User = Depends(_staff), db: Session = Depends(get_db)):
    """Impor TCML hasil LLM eksternal (paket diekspor .md -> ditempel di sini).

    Dokumen dipecah & divalidasi 2 lapis terhadap paket, lalu menjadi draf —
    alur lanjutan (perbaiki/simpan/terbitkan) sama seperti draf generate.
    """
    pack = db.get(ParserPack, body.pack_id)
    if pack is None or not can_access_pack(db, user, pack):
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan.")
    if body.kind == "dokumen":
        teks_bersih = "\n".join(
            ln for ln in body.teks.splitlines() if not ln.strip().startswith("```")
        ).strip()
        docs = [normalisasi_format_kuis(teks_bersih)] if teks_bersih else []
    else:
        docs = [normalisasi_format_kuis(t) for t in split_documents(body.teks)]
    if not docs:
        raise HTTPException(
            status_code=400,
            detail="Tidak ditemukan dokumen TCML (root block) pada teks yang ditempel.",
        )
    job = GenerationJob(
        user_id=user.id,
        pack_id=pack.id,
        ai_setting_id=None,
        brief={"impor": True, "kind": body.kind},
        prompt_final=None,
        status="done",
        raw_output=body.teks,
        finished_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    drafts: list[ContentDraft] = []
    for teks in docs:
        if body.kind == "dokumen":
            v = validate_bundle_document(db, pack, teks)
            d = ContentDraft(
                generation_job_id=job.id,
                user_id=user.id,
                jenis="dokumen",
                tipe_quiz=None,
                judul=v["judul"],
                teks_mentah=teks,
                is_valid=v["valid"],
                errors=v["errors"],
                status="draft",
            )
        else:
            v = validate_document(db, pack, body.kind, teks)
            d = ContentDraft(
                generation_job_id=job.id,
                user_id=user.id,
                jenis=v["jenis"] or ("quiz" if body.kind != "materi" else "material"),
                tipe_quiz=v["tipe_quiz"],
                judul=v["judul"],
                teks_mentah=teks,
                is_valid=v["valid"],
                errors=v["errors"],
                status="draft",
            )
        db.add(d)
        drafts.append(d)
    db.commit()
    for d in drafts:
        db.refresh(d)
    return {"job_id": job.id, "pack_id": pack.id, "drafts": [draft_out(d) for d in drafts]}


@router.get("/drafts")
def list_drafts(user: User = Depends(_staff), db: Session = Depends(get_db)):
    rows = (
        db.query(ContentDraft)
        .filter(ContentDraft.user_id == user.id)
        .order_by(ContentDraft.id.desc())
        .limit(50)
        .all()
    )
    return [draft_out(d) for d in rows]


@router.delete("/drafts/{draft_id}", dependencies=[Depends(require_csrf)])
def delete_draft(draft_id: int, user: User = Depends(_staff), db: Session = Depends(get_db)):
    d = _own_draft(db, user, draft_id)
    db.delete(d)
    db.commit()
    return {"ok": True}


def _repair_count(db: Session, draft_id: int) -> int:
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "draft.repair",
            AuditLog.target_type == "content_draft",
            AuditLog.target_id == draft_id,
        )
        .count()
    )


@router.post("/drafts/{draft_id}/repair", dependencies=[Depends(require_csrf)])
def repair_draft(draft_id: int, user: User = Depends(_staff), db: Session = Depends(get_db)):
    d = _own_draft(db, user, draft_id)
    if d.is_valid:
        raise HTTPException(status_code=400, detail="Draf ini sudah valid; tidak perlu diperbaiki.")
    if _repair_count(db, draft_id) >= MAX_REPAIR:
        raise HTTPException(
            status_code=400,
            detail=f"Batas perbaikan otomatis ({MAX_REPAIR}x) tercapai. Edit manual lewat editor — teks draf bisa disalin dari sini.",
        )
    job = db.get(GenerationJob, d.generation_job_id) if d.generation_job_id else None
    pack = db.get(ParserPack, job.pack_id) if job and job.pack_id else None
    setting = _resolve_setting(db, user, job.ai_setting_id if job else None)
    # Jenis target diambil dari PERMINTAAN AWAL di brief job — BUKAN dari
    # tipe yang terdeteksi pada draf rusak. Dulu: draf kuis esai yang
    # terlanjur berisi PG membuat repair mengejar PG, lalu validasi esai
    # menolaknya lagi (mismatch bolak-balik, tidak pernah konvergen).
    kind_job = (job.brief or {}).get("kind") if job else None
    if kind_job in ("materi", "kuis_pg", "kuis_esai", "dokumen"):
        kind = kind_job
    else:
        kind = (
            "dokumen"
            if d.jenis == "dokumen"
            else "materi"
            if d.jenis == "material"
            else ("kuis_pg" if d.tipe_quiz == "pilihan_ganda" else "kuis_esai")
        )
    system_prompt = (
        build_system_prompt(db, pack, kind)
        if pack is not None
        else "Kamu adalah penulis konten pembelajaran yang menulis dokumen TCML Lifunze."
    )
    error_lines = "\n".join(
        f"- Baris {e.get('line')}: {e['message']}" if e.get("line") else f"- {e['message']}"
        for e in (d.errors or [])
    )
    if kind == "dokumen":
        penutup = (
            "Perbaiki dokumen TERPADU tersebut (pertahankan bagian materi dan kuisnya). "
            "Keluarkan HANYA dokumen TCML gabungan yang sudah diperbaiki, tanpa penjelasan apa pun."
        )
    else:
        penutup = (
            "Perbaiki dokumen tersebut. Keluarkan HANYA satu dokumen TCML yang sudah diperbaiki, "
            "tanpa penjelasan apa pun."
        )
    if kind == "kuis_pg":
        penutup += (
            " PENTING: hasil akhir WAJIB kuis pilihan ganda — baris [TYPE]pilihan_ganda[/TYPE], "
            "setiap soal dibungkus [QUESTION n]...[/QUESTION n] dan punya [OPTIONS] + [ANSWER]. "
            "Bila dokumen lama bertipe lain, KONVERSI seluruhnya ke pilihan ganda."
        )
    elif kind == "kuis_esai":
        penutup += (
            " PENTING: hasil akhir WAJIB kuis esai/teks — baris [TYPE]essay[/TYPE], setiap soal "
            "dibungkus [QUESTION n]...[/QUESTION n] TANPA [OPTIONS], dan [ANSWER] berisi jawaban "
            "referensi singkat. Bila dokumen lama pilihan ganda, KONVERSI seluruhnya: buang semua "
            "[OPTIONS] dan tulis ulang [ANSWER] sebagai referensi (bukan huruf kunci)."
        )
    user_prompt = (
        "Dokumen TCML berikut GAGAL validasi dengan error:\n"
        f"{error_lines}\n\nDOKUMEN:\n{d.teks_mentah}\n\n"
        f"{penutup}"
    )
    try:
        raw = chat_completion(
            setting,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if kind == "dokumen":
        new_text = "\n".join(
            ln for ln in raw.splitlines() if not ln.strip().startswith("```")
        ).strip()
    else:
        docs = split_documents(raw)
        new_text = docs[0] if docs else raw.strip()
    new_text = normalisasi_format_kuis(new_text)
    if pack is not None:
        if kind == "dokumen":
            v = validate_bundle_document(db, pack, new_text)
            d.teks_mentah = new_text
            d.is_valid = v["valid"]
            d.errors = v["errors"]
            d.judul = v["judul"]
        else:
            v = validate_document(db, pack, kind, new_text)
            d.teks_mentah = new_text
            d.is_valid = v["valid"]
            d.errors = v["errors"]
            d.judul = v["judul"]
            d.tipe_quiz = v["tipe_quiz"] or d.tipe_quiz
    else:
        d.teks_mentah = new_text
    write_audit(db, user.id, "draft.repair", "content_draft", d.id)
    db.commit()
    db.refresh(d)
    return draft_out(d)


class SaveBankIn(BaseModel):
    judul: Optional[str] = None


@router.post("/drafts/{draft_id}/save-bank", status_code=201, dependencies=[Depends(require_csrf)])
def save_draft_to_bank(
    draft_id: int,
    body: SaveBankIn,
    user: User = Depends(_staff),
    db: Session = Depends(get_db),
):
    d = _own_draft(db, user, draft_id)
    if not d.is_valid:
        raise HTTPException(status_code=400, detail="Draf belum valid — perbaiki dulu sebelum disimpan.")
    _tolak_sudah_final(d)
    judul = (body.judul or d.judul).strip()
    if d.jenis == "dokumen":
        import uuid as _uuid

        from ..tcml.document import split_document

        parts = split_document(d.teks_mentah)
        if parts["errors"] or not any(
            parts[k] for k in ("materi", "kuis_pg", "kuis_esai")
        ):
            raise HTTPException(status_code=400, detail="Dokumen terpadu tidak terbaca bagiannya.")
        grup = _uuid.uuid4().hex
        jenis_dok = _jenis_dokumen_draf(db, d)
        preset = _pengaturan_generate(jenis_dok)
        first_id = None
        if parts["materi"]:
            _material_parse_or_400(parts["materi"])
            saved_m = SavedMaterial(
                judul=judul, teks_mentah=parts["materi"], dibuat_oleh=user.id,
                grup_dokumen=grup, jenis=jenis_dok,
            )
            db.add(saved_m)
            db.flush()
            first_id = saved_m.id
        for key, tipe in (("kuis_pg", "pilihan_ganda"), ("kuis_esai", "teks")):
            if parts[key]:
                parsed = _quiz_parse_or_400(parts[key], tipe)
                saved_q = SavedQuiz(
                    judul=judul,
                    tipe=tipe,
                    teks_mentah=parts[key],
                    snapshot=parsed["questions"],
                    dibuat_oleh=user.id,
                    grup_dokumen=grup,
                    jenis=jenis_dok,
                    durasi_menit=preset.durasi_menit,
                    acak_soal=preset.acak_soal,
                    acak_opsi=preset.acak_opsi,
                    tampilkan_kunci=preset.tampilkan_kunci,
                )
                db.add(saved_q)
                db.flush()
                if first_id is None:
                    first_id = saved_q.id
        d.published_id = first_id
        d.status = "published"
        db.commit()
        return {"ok": True, "draft": draft_out(d), "saved_id": d.published_id, "jenis": d.jenis, "grup": grup}
    if d.jenis == "material":
        _material_parse_or_400(d.teks_mentah)
        saved = SavedMaterial(judul=judul, teks_mentah=d.teks_mentah, dibuat_oleh=user.id)
        db.add(saved)
        db.flush()
        d.published_id = saved.id
    else:
        parsed = _quiz_parse_or_400(d.teks_mentah, d.tipe_quiz or "pilihan_ganda")
        saved = SavedQuiz(
            judul=judul,
            tipe=d.tipe_quiz or "pilihan_ganda",
            teks_mentah=d.teks_mentah,
            snapshot=parsed["questions"],
            dibuat_oleh=user.id,
        )
        db.add(saved)
        db.flush()
        d.published_id = saved.id
    d.status = "published"
    db.commit()
    return {"ok": True, "draft": draft_out(d), "saved_id": d.published_id, "jenis": d.jenis}


class PublishIn(BaseModel):
    meeting_id: int
    judul: Optional[str] = None


@router.post("/drafts/{draft_id}/publish", status_code=201, dependencies=[Depends(require_csrf)])
def publish_draft(
    draft_id: int,
    body: PublishIn,
    user: User = Depends(_staff),
    db: Session = Depends(get_db),
):
    d = _own_draft(db, user, draft_id)
    if not d.is_valid:
        raise HTTPException(status_code=400, detail="Draf belum valid — perbaiki dulu sebelum diterbitkan.")
    _tolak_sudah_final(d)
    meeting = get_meeting(db, body.meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    judul = (body.judul or d.judul).strip()
    if d.jenis == "dokumen":
        import uuid as _uuid

        from ..tcml.document import split_document
        from .documents import QuizSettingsIn, buat_kuis_part, buat_material_part

        parts = split_document(d.teks_mentah)
        if parts["errors"] or not any(
            parts[k] for k in ("materi", "kuis_pg", "kuis_esai")
        ):
            raise HTTPException(status_code=400, detail="Dokumen terpadu tidak terbaca bagiannya.")
        grup = _uuid.uuid4().hex
        jenis_dok = _jenis_dokumen_draf(db, d)
        m_id = q_id = None
        if parts["materi"]:
            m = buat_material_part(
                db, meeting, user,
                judul=judul, teks=parts["materi"], grup=grup,
                jenis=jenis_dok, tenggat=None,
            )
            m_id = m.id
        for key, tipe in (("kuis_pg", "pilihan_ganda"), ("kuis_esai", "teks")):
            if parts[key]:
                q = buat_kuis_part(
                    db, meeting, user,
                    judul=judul, teks=parts[key], tipe=tipe, grup=grup,
                    jenis=jenis_dok, pengaturan=_pengaturan_generate(jenis_dok),
                )
                if q_id is None:
                    q_id = q.id
        d.published_id = m_id or q_id
        d.status = "published"
        db.commit()
        return {
            "ok": True,
            "draft": draft_out(d),
            "grup": grup,
            "material_id": m_id,
            "quiz_id": q_id,
        }
    if d.jenis == "material":
        html = _material_parse_or_400(d.teks_mentah)
        m = Material(
            meeting_id=meeting.id,
            judul=judul,
            teks_mentah=d.teks_mentah,
            rendered_html=html,
            dibuat_oleh=user.id,
        )
        db.add(m)
        db.flush()
        d.published_id = m.id
        target = {"material_id": m.id}
    else:
        tipe = d.tipe_quiz or "pilihan_ganda"
        parsed = _quiz_parse_or_400(d.teks_mentah, tipe)
        q = Quiz(meeting_id=meeting.id, judul=judul, tipe=tipe, teks_mentah=d.teks_mentah, dibuat_oleh=user.id)
        db.add(q)
        db.flush()
        _create_questions(db, q, parsed["questions"])
        _notify_quiz_baru(db, q)  # audit #8: dulu terbit kuis dari Generate tidak memberi tahu siswa
        d.published_id = q.id
        target = {"quiz_id": q.id}
    d.status = "published"
    db.commit()
    return {"ok": True, "draft": draft_out(d), **target}
