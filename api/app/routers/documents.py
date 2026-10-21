"""Dokumen terpadu: satu dokumen = bagian materi (opsional) + bagian kuis
PG/esai (opsional) yang berbagi grup_dokumen.

Pengalaman guru disatukan (satu editor, satu baris di kelas, satu entri di
bank), sementara mesin lama tetap utuh: bagian materi adalah baris Material
biasa, bagian kuis adalah baris Quiz biasa — pengerjaan, penilaian,
progress, ekspor, dan template tetap bekerja seperti sebelumnya.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import (
    get_meeting,
    get_subject,
    require_subject_manage,
    require_subject_view,
)
from ..db import get_db
from ..deps import get_current_user, require_csrf
from ..models import (
    CekAnswer,
    Material,
    Meeting,
    Quiz,
    QuizAttempt,
    SavedMaterial,
    SavedQuiz,
    Submission,
    User,
)
from ..tcml import parse_material
from ..tcml.quiz import parse_quiz_v2
from .bank import _validate_category
from .materials import material_out, pagar_cek
from .quizzes import (
    _as_utc,
    _create_questions,
    _notify_quiz_baru,
    _parse_or_400 as _parse_kuis_or_400,
    _questions_of,
    _quiz_full_out,
    quiz_settings_out,
)

router = APIRouter(tags=["documents"])

JENIS_VALID = ("materi", "tugas", "kuis", "ujian")


class QuizSettingsIn(BaseModel):
    durasi_menit: Optional[int] = Field(default=None, ge=1)
    acak_soal: bool = False
    acak_opsi: bool = False
    dibuka_pada: Optional[datetime] = None
    ditutup_pada: Optional[datetime] = None
    tampilkan_kunci: bool = True


class DocumentIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    jenis: str = Field(pattern="^(materi|tugas|kuis|ujian)$")
    tenggat: Optional[datetime] = None
    teks_materi: Optional[str] = None
    teks_kuis_pg: Optional[str] = None
    teks_kuis_esai: Optional[str] = None
    pengaturan_kuis: QuizSettingsIn = QuizSettingsIn()


# ------------------------------------------------------------------ helpers
def _anggota(db: Session, grup: str) -> tuple[Material | None, list[Quiz]]:
    material = db.query(Material).filter(Material.grup_dokumen == grup).first()
    quizzes = (
        db.query(Quiz).filter(Quiz.grup_dokumen == grup).order_by(Quiz.id).all()
    )
    return material, quizzes


def _anchor(material: Material | None, quizzes: list[Quiz]):
    anchor = material or (quizzes[0] if quizzes else None)
    if anchor is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    return anchor


def _quiz_meta_out(q: Quiz) -> dict:
    """Metadata kuis TANPA soal/kunci — aman untuk siswa (audit #1)."""
    return {
        "id": q.id,
        "judul": q.judul,
        "tipe": q.tipe,
        "dibuka_pada": q.dibuka_pada.isoformat() if q.dibuka_pada else None,
        "ditutup_pada": q.ditutup_pada.isoformat() if q.ditutup_pada else None,
        "durasi_menit": q.durasi_menit,
    }


def document_out(db: Session, grup: str, user: User | None = None) -> dict:
    material, quizzes = _anggota(db, grup)
    anchor = _anchor(material, quizzes)
    meeting = db.get(Meeting, anchor.meeting_id)
    # Audit #1: siswa hanya boleh menerima proyeksi aman — tanpa teks_mentah
    # (memuat kunci [CEK]) dan tanpa soal/kunci kuis versi staf.
    untuk_siswa = user is not None and user.role == "siswa"
    material_payload = (
        material_out(material, meeting.subject_id if meeting else None)
        if material
        else None
    )
    if untuk_siswa and material_payload is not None:
        material_payload["teks_mentah"] = None
    return {
        "grup": grup,
        "meeting_id": anchor.meeting_id,
        "subject_id": meeting.subject_id if meeting else None,
        "judul": anchor.judul,
        "jenis": anchor.jenis,
        "tenggat": (
            material.tenggat.isoformat() if material and material.tenggat else None
        ),
        "material": material_payload,
        "quizzes": (
            [_quiz_meta_out(q) for q in quizzes]
            if untuk_siswa
            else [_quiz_full_out(db, q) for q in quizzes]
        ),
        "pengaturan_kuis": (
            quiz_settings_out(quizzes[0])
            if quizzes
            else {
                "durasi_menit": None,
                "acak_soal": False,
                "acak_opsi": False,
                "dibuka_pada": None,
                "ditutup_pada": None,
                "tampilkan_kunci": True,
            }
        ),
    }


def _parse_materi_or_400(teks: str) -> str:
    res = parse_material(teks)
    if not res["success"]:
        raise HTTPException(
            status_code=400,
            detail={"pesan": "Bagian materi tidak valid.", "errors": res["errors"]},
        )
    return res["content"]


def _pengaturan_berubah(quiz: Quiz, s: QuizSettingsIn) -> bool:
    """True bila pengaturan pengerjaan pada `s` berbeda dari yang tersimpan."""
    if (
        quiz.durasi_menit != s.durasi_menit
        or quiz.acak_soal != s.acak_soal
        or quiz.acak_opsi != s.acak_opsi
        or quiz.tampilkan_kunci != s.tampilkan_kunci
    ):
        return True
    for field in ("dibuka_pada", "ditutup_pada"):
        lama = getattr(quiz, field)
        baru = getattr(s, field)
        if (lama is None) != (baru is None):
            return True
        if lama is not None and baru is not None and _as_utc(lama) != _as_utc(baru):
            return True
    return False


def _terapkan_pengaturan(quiz: Quiz, s: QuizSettingsIn) -> None:
    quiz.durasi_menit = s.durasi_menit
    quiz.acak_soal = s.acak_soal
    quiz.acak_opsi = s.acak_opsi
    quiz.dibuka_pada = s.dibuka_pada
    quiz.ditutup_pada = s.ditutup_pada
    quiz.tampilkan_kunci = s.tampilkan_kunci


def buat_material_part(
    db: Session,
    meeting: Meeting,
    user: User,
    *,
    judul: str,
    teks: str,
    grup: str,
    jenis: str,
    tenggat: Optional[datetime],
) -> Material:
    html = _parse_materi_or_400(teks)
    m = Material(
        meeting_id=meeting.id,
        judul=judul.strip(),
        teks_mentah=teks,
        rendered_html=html,
        dibuat_oleh=user.id,
        grup_dokumen=grup,
        jenis=jenis,
        tenggat=tenggat,
    )
    db.add(m)
    db.flush()
    return m


def buat_kuis_part(
    db: Session,
    meeting: Meeting,
    user: User,
    *,
    judul: str,
    teks: str,
    tipe: str,
    grup: str,
    jenis: str,
    pengaturan: QuizSettingsIn,
) -> Quiz:
    parsed = _parse_kuis_or_400(teks, tipe)
    q = Quiz(
        meeting_id=meeting.id,
        judul=judul.strip(),
        tipe=tipe,
        teks_mentah=teks,
        dibuat_oleh=user.id,
        grup_dokumen=grup,
        jenis=jenis,
    )
    _terapkan_pengaturan(q, pengaturan)
    db.add(q)
    db.flush()
    _create_questions(db, q, parsed["questions"])
    _notify_quiz_baru(db, q)
    return q


def _ada_bagian(body: DocumentIn) -> bool:
    return any(
        (t or "").strip()
        for t in (body.teks_materi, body.teks_kuis_pg, body.teks_kuis_esai)
    )


# ------------------------------------------------------------------ endpoints
@router.post(
    "/api/v1/meetings/{meeting_id}/documents",
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_document(
    meeting_id: int,
    body: DocumentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = get_meeting(db, meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    if not _ada_bagian(body):
        raise HTTPException(
            status_code=400,
            detail="Dokumen kosong — isi bagian materi atau kuis dulu.",
        )
    grup = uuid.uuid4().hex
    if (body.teks_materi or "").strip():
        buat_material_part(
            db, meeting, user,
            judul=body.judul, teks=body.teks_materi, grup=grup,
            jenis=body.jenis, tenggat=body.tenggat,
        )
    if (body.teks_kuis_pg or "").strip():
        buat_kuis_part(
            db, meeting, user,
            judul=body.judul, teks=body.teks_kuis_pg, tipe="pilihan_ganda",
            grup=grup, jenis=body.jenis, pengaturan=body.pengaturan_kuis,
        )
    if (body.teks_kuis_esai or "").strip():
        buat_kuis_part(
            db, meeting, user,
            judul=body.judul, teks=body.teks_kuis_esai, tipe="teks",
            grup=grup, jenis=body.jenis, pengaturan=body.pengaturan_kuis,
        )
    db.commit()
    return document_out(db, grup)


@router.get("/api/v1/documents/{grup}")
def get_document(
    grup: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material, quizzes = _anggota(db, grup)
    anchor = _anchor(material, quizzes)
    meeting = db.get(Meeting, anchor.meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_view(db, user, subject)
    return document_out(db, grup, user)


@router.patch("/api/v1/documents/{grup}", dependencies=[Depends(require_csrf)])
def update_document(
    grup: str,
    body: DocumentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material, quizzes = _anggota(db, grup)
    anchor = _anchor(material, quizzes)
    meeting = db.get(Meeting, anchor.meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    if not _ada_bagian(body):
        raise HTTPException(
            status_code=400,
            detail="Dokumen tidak boleh kosong — hapus dokumen bila tidak dipakai lagi.",
        )

    # --- bagian materi ---
    teks_materi = (body.teks_materi or "").strip()
    if teks_materi:
        if material is not None:
            material.judul = body.judul.strip()
            if body.teks_materi != material.teks_mentah:
                pagar_cek(db, material, body.teks_materi)  # audit #4
                material.teks_mentah = body.teks_materi
                material.rendered_html = _parse_materi_or_400(body.teks_materi)
            material.jenis = body.jenis
            material.tenggat = body.tenggat
        else:
            material = buat_material_part(
                db, meeting, user,
                judul=body.judul, teks=body.teks_materi, grup=grup,
                jenis=body.jenis, tenggat=body.tenggat,
            )
    elif material is not None:
        punya_lampiran = len(material.files) > 0
        punya_kumpul = (
            db.query(Submission).filter(Submission.material_id == material.id).first()
            is not None
        )
        punya_jawaban_cek = (
            db.query(CekAnswer).filter(CekAnswer.material_id == material.id).first()
            is not None
        )
        if punya_lampiran or punya_kumpul or punya_jawaban_cek:
            raise HTTPException(
                status_code=400,
                detail="Bagian materi punya lampiran/pengumpulan/jawaban Cek Pemahaman siswa — tidak bisa dikosongkan dari dokumen.",
            )
        db.delete(material)
        material = None

    # --- bagian kuis ---
    by_tipe = {q.tipe: q for q in quizzes}
    for tipe, teks in (
        ("pilihan_ganda", body.teks_kuis_pg),
        ("teks", body.teks_kuis_esai),
    ):
        teks_bersih = (teks or "").strip()
        existing = by_tipe.get(tipe)
        if teks_bersih:
            if existing is not None:
                existing.judul = body.judul.strip()
                existing.jenis = body.jenis
                # Audit #10/#32: pengaturan dikunci begitu ada attempt.
                if _pengaturan_berubah(existing, body.pengaturan_kuis):
                    ada_attempt = (
                        db.query(QuizAttempt)
                        .filter(QuizAttempt.quiz_id == existing.id)
                        .first()
                    )
                    if ada_attempt is not None:
                        raise HTTPException(
                            status_code=400,
                            detail="Pengaturan kuis tidak bisa diubah: sudah ada siswa yang mengerjakan kuis ini.",
                        )
                _terapkan_pengaturan(existing, body.pengaturan_kuis)
                if teks != existing.teks_mentah:
                    ada_attempt = (
                        db.query(QuizAttempt)
                        .filter(QuizAttempt.quiz_id == existing.id)
                        .first()
                    )
                    if ada_attempt is not None:
                        raise HTTPException(
                            status_code=400,
                            detail="Soal tidak bisa diubah: sudah ada siswa yang mengerjakan kuis ini.",
                        )
                    parsed = _parse_kuis_or_400(teks, tipe)
                    for q in _questions_of(db, existing):
                        db.delete(q)
                    db.flush()
                    existing.teks_mentah = teks
                    _create_questions(db, existing, parsed["questions"])
            else:
                buat_kuis_part(
                    db, meeting, user,
                    judul=body.judul, teks=teks, tipe=tipe,
                    grup=grup, jenis=body.jenis, pengaturan=body.pengaturan_kuis,
                )
        elif existing is not None:
            ada_attempt = (
                db.query(QuizAttempt)
                .filter(QuizAttempt.quiz_id == existing.id)
                .first()
            )
            if ada_attempt is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Bagian kuis sudah dikerjakan siswa — tidak bisa dihapus dari dokumen.",
                )
            db.delete(existing)

    db.commit()
    return document_out(db, grup)


@router.delete("/api/v1/documents/{grup}", dependencies=[Depends(require_csrf)])
def delete_document(
    grup: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material, quizzes = _anggota(db, grup)
    anchor = _anchor(material, quizzes)
    meeting = db.get(Meeting, anchor.meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    for q in quizzes:
        db.delete(q)
    if material is not None:
        db.delete(material)
    db.commit()
    return {"pesan": "Dokumen dihapus."}


class SaveToBankIn(BaseModel):
    kategori_id: Optional[int] = None


@router.post(
    "/api/v1/documents/{grup}/save-to-bank",
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def save_document_to_bank(
    grup: str,
    body: SaveToBankIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simpan dokumen kelas ke bank sebagai satu dokumen bank (pasangan).

    Mengikuti aturan penanda asal: sekali tersimpan, dokumen tidak bisa
    disimpan lagi walau diedit.
    """
    material, quizzes = _anggota(db, grup)
    anchor = _anchor(material, quizzes)
    meeting = db.get(Meeting, anchor.meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    _validate_category(db, user, body.kategori_id)

    if material is not None and (
        db.query(SavedMaterial)
        .filter(SavedMaterial.dibuat_oleh == user.id, SavedMaterial.asal_id == material.id)
        .first()
        is not None
    ):
        raise HTTPException(status_code=400, detail="Dokumen ini sudah tersimpan di bank.")
    for q in quizzes:
        if (
            db.query(SavedQuiz)
            .filter(SavedQuiz.dibuat_oleh == user.id, SavedQuiz.asal_id == q.id)
            .first()
            is not None
        ):
            raise HTTPException(status_code=400, detail="Dokumen ini sudah tersimpan di bank.")

    bank_grup = uuid.uuid4().hex
    if material is not None:
        db.add(
            SavedMaterial(
                judul=material.judul,
                teks_mentah=material.teks_mentah,
                dibuat_oleh=user.id,
                kategori_id=body.kategori_id,
                asal_id=material.id,
                grup_dokumen=bank_grup,
                jenis=anchor.jenis,
            )
        )
    for q in quizzes:
        res = parse_quiz_v2(q.teks_mentah, expected_type=q.tipe)
        db.add(
            SavedQuiz(
                judul=q.judul,
                tipe=q.tipe,
                teks_mentah=q.teks_mentah,
                snapshot=res["content"]["questions"] if res["success"] else [],
                dibuat_oleh=user.id,
                kategori_id=body.kategori_id,
                asal_id=q.id,
                grup_dokumen=bank_grup,
                jenis=anchor.jenis,
                # Audit #9: pengaturan pengerjaan ikut tersimpan di bank.
                durasi_menit=q.durasi_menit,
                acak_soal=q.acak_soal,
                acak_opsi=q.acak_opsi,
                tampilkan_kunci=q.tampilkan_kunci,
            )
        )
    db.commit()
    return {"grup": bank_grup, "pesan": "Dokumen tersimpan di bank."}
