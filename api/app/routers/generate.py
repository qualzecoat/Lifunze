"""Router Generate AI (Fase 5).

Alur: guru memilih paket parser + Pengaturan AI + brief -> prompt dirakit
HANYA dari modul paket -> AI menjawab (boleh bundle multi-dokumen) ->
keluaran dipecah per root block -> tiap dokumen divalidasi 2 lapis ->
tersimpan sebagai ContentDraft. Draf TIDAK pernah terbit otomatis: guru
meninjau, memperbaiki (manual atau self-repair AI, maks 2x), lalu menyimpan
ke bank atau menerbitkan ke pertemuan.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import get_meeting, get_subject, require_subject_manage
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
    Quiz,
    SavedMaterial,
    SavedQuiz,
    User,
)
from ..paket import (
    build_system_prompt,
    can_access_pack,
    pack_module_rows,
    split_documents,
    validate_bundle_document,
    validate_document,
)
from ..tcml.quiz import parse_quiz_v2
from .materials import _parse_or_400 as _material_parse_or_400
from .quizzes import _create_questions
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


def _resolve_setting(db: Session, user: User, setting_id: Optional[int]) -> AiSetting:
    q = db.query(AiSetting).filter(AiSetting.user_id == user.id)
    if setting_id is not None:
        s = q.filter(AiSetting.id == setting_id).first()
        if s is None:
            raise HTTPException(status_code=404, detail="Pengaturan AI tidak ditemukan.")
        return s
    s = q.filter(AiSetting.is_default.is_(True)).first() or q.first()
    if s is None:
        raise HTTPException(
            status_code=400,
            detail="Anda belum punya Pengaturan AI. Buat dulu di menu Pengaturan AI (base URL, API key, model).",
        )
    return s


def _brief_to_user_prompt(kind: str, brief: dict, slugs: list[str] | None = None) -> str:
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
            target = (
                f"satu DOKUMEN {nama} betulan: root [QUIZ] yang diawali blok pengantar "
                "(paragraf sambutan/konteks dan [NOTE] petunjuk pengerjaan"
                + (", [WARNING] aturan ujian" if jenis_dok == "ujian" else "")
                + ") lalu soal-soalnya; boleh didahului satu root [MATERIAL] bacaan "
                "pendamping singkat bila materinya memang perlu dibaca dulu"
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
    if kind in ("kuis_pg", "kuis_esai", "dokumen") and brief.get("jumlah_soal"):
        lines.append(f"Jumlah soal: {brief['jumlah_soal']}.")
    if instruksi:
        lines.append(f"Instruksi tambahan: {instruksi}")
    return "\n".join(lines)


class GenerateIn(BaseModel):
    kind: str = Field(pattern="^(materi|kuis_pg|kuis_esai|dokumen)$")
    pack_id: int
    ai_setting_id: Optional[int] = None
    brief: dict = Field(default_factory=dict)


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def generate(body: GenerateIn, user: User = Depends(_staff), db: Session = Depends(get_db)):
    if not (body.brief.get("topik") or "").strip():
        raise HTTPException(status_code=400, detail="Brief wajib berisi topik.")
    pack = db.get(ParserPack, body.pack_id)
    if pack is None or not can_access_pack(db, user, pack):
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan.")
    setting = _resolve_setting(db, user, body.ai_setting_id)

    system_prompt = build_system_prompt(db, pack, body.kind)
    slugs = [m.slug for m in pack_module_rows(db, pack)]
    user_prompt = _brief_to_user_prompt(body.kind, body.brief, slugs)
    job = GenerationJob(
        user_id=user.id,
        pack_id=pack.id,
        ai_setting_id=setting.id,
        brief={**body.brief, "kind": body.kind},
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
        docs = [teks_bersih] if teks_bersih else []
    else:
        docs = split_documents(body.teks)
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
        first_id = None
        if parts["materi"]:
            _material_parse_or_400(parts["materi"])
            saved_m = SavedMaterial(
                judul=judul, teks_mentah=parts["materi"], dibuat_oleh=user.id,
                grup_dokumen=grup, jenis="materi",
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
                    jenis="materi",
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
        m_id = q_id = None
        if parts["materi"]:
            m = buat_material_part(
                db, meeting, user,
                judul=judul, teks=parts["materi"], grup=grup,
                jenis="materi", tenggat=None,
            )
            m_id = m.id
        for key, tipe in (("kuis_pg", "pilihan_ganda"), ("kuis_esai", "teks")):
            if parts[key]:
                q = buat_kuis_part(
                    db, meeting, user,
                    judul=judul, teks=parts[key], tipe=tipe, grup=grup,
                    jenis="materi", pengaturan=QuizSettingsIn(),
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
        d.published_id = q.id
        target = {"quiz_id": q.id}
    d.status = "published"
    db.commit()
    return {"ok": True, "draft": draft_out(d), **target}
