"""Router Kuis v2 (Fase 3).

Alur: guru menyusun kuis TCML -> parse_quiz_v2 -> questions/options
ternormalisasi. Siswa mengerjakan lewat attempt (jendela waktu + durasi
dihormati, urutan soal/opsi bisa diacak deterministik per attempt).
PG dinilai otomatis berbobot (multi-jawaban-benar = himpunan harus persis);
esai dinilai manual guru per soal. Hasil bisa diekspor CSV/XLSX.

Penyimpanan jawaban: satu AttemptAnswer per soal.
- PG   : jawaban_teks = JSON list id opsi terpilih, mis. "[3, 7]"
- Esai : jawaban_teks = teks jawaban siswa
"""

import io
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..access import get_meeting, get_subject, require_subject_manage, require_subject_view
from ..db import get_db
from ..deps import get_current_user, require_csrf
from ..models import (
    AttemptAnswer,
    BankQuestion,
    Enrollment,
    Material,
    Question,
    QuestionOption,
    Quiz,
    QuizAttempt,
    SavedQuiz,
    User,
)
from ..notify import notify
from ..tcml.quiz import parse_quiz_v2
from .bank import _validate_category

router = APIRouter(tags=["quizzes"])

GRACE_SECONDS = 30  # toleransi keterlambatan submit setelah durasi habis


# ------------------------------------------------------------------ helpers
def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_quiz(db: Session, quiz_id: int) -> Quiz:
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Kuis tidak ditemukan.")
    return quiz


def _subject_of_quiz(db: Session, quiz: Quiz):
    meeting = get_meeting(db, quiz.meeting_id)
    return get_subject(db, meeting.subject_id), meeting


def _parse_or_400(teks: str, tipe: str) -> dict:
    res = parse_quiz_v2(teks, expected_type=tipe)
    if not res["success"]:
        raise HTTPException(
            status_code=400,
            detail={"pesan": "Teks TCML kuis tidak valid.", "errors": res["errors"]},
        )
    return res["content"]


def _notify_quiz_baru(db: Session, quiz: Quiz) -> None:
    """Notifikasi kuis baru ke semua siswa terdaftar pada mapel kuis ini."""
    meeting = get_meeting(db, quiz.meeting_id)
    enrolled = (
        db.query(Enrollment).filter(Enrollment.subject_id == meeting.subject_id).all()
    )
    notify(
        db,
        [e.student_id for e in enrolled],
        "kuis_baru",
        {"quiz_id": quiz.id, "subject_id": meeting.subject_id, "judul": quiz.judul},
    )


def _create_questions(db: Session, quiz: Quiz, parsed_questions: list) -> None:
    for i, q in enumerate(parsed_questions):
        question = Question(
            quiz_id=quiz.id,
            tipe=q["tipe"],
            pertanyaan=q["pertanyaan"],
            urutan=i,
            bobot=q["bobot"],
            jawaban_referensi=q.get("jawaban_referensi"),
        )
        db.add(question)
        db.flush()
        for o in q.get("options", []):
            db.add(
                QuestionOption(
                    question_id=question.id,
                    label=o["label"],
                    teks=o["teks"],
                    is_correct=o["is_correct"],
                )
            )


def _questions_of(db: Session, quiz: Quiz) -> list[Question]:
    return (
        db.query(Question)
        .filter(Question.quiz_id == quiz.id)
        .order_by(Question.urutan)
        .all()
    )


def question_full_out(q: Question) -> dict:
    return {
        "id": q.id,
        "tipe": q.tipe,
        "pertanyaan": q.pertanyaan,
        "bobot": q.bobot,
        "jawaban_referensi": q.jawaban_referensi,
        "options": [
            {"id": o.id, "label": o.label, "teks": o.teks, "is_correct": o.is_correct}
            for o in q.options
        ],
    }


def quiz_settings_out(quiz: Quiz) -> dict:
    return {
        "durasi_menit": quiz.durasi_menit,
        "acak_soal": quiz.acak_soal,
        "acak_opsi": quiz.acak_opsi,
        "dibuka_pada": _as_utc(quiz.dibuka_pada).isoformat() if quiz.dibuka_pada else None,
        "ditutup_pada": _as_utc(quiz.ditutup_pada).isoformat() if quiz.ditutup_pada else None,
        "tampilkan_kunci": quiz.tampilkan_kunci,
    }


# ------------------------------------------------------------------ CRUD kuis
class QuizIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    tipe: str = Field(pattern="^(pilihan_ganda|teks)$")
    teks_mentah: str = Field(min_length=1)
    durasi_menit: Optional[int] = Field(default=None, ge=1)
    acak_soal: bool = False
    acak_opsi: bool = False
    dibuka_pada: Optional[datetime] = None
    ditutup_pada: Optional[datetime] = None
    tampilkan_kunci: bool = True


def _apply_settings(quiz: Quiz, body: QuizIn) -> None:
    quiz.durasi_menit = body.durasi_menit
    quiz.acak_soal = body.acak_soal
    quiz.acak_opsi = body.acak_opsi
    quiz.dibuka_pada = body.dibuka_pada
    quiz.ditutup_pada = body.ditutup_pada
    quiz.tampilkan_kunci = body.tampilkan_kunci


def _apply_saved_settings(quiz: Quiz, saved: SavedQuiz) -> None:
    """Audit #9: pengaturan pengerjaan dari kuis bank diterapkan kembali
    (durasi/acak/tampilkan kunci). Jendela buka/tutup TIDAK disalin karena
    itu jadwal untuk kelas asal, bukan sifat kuisnya."""
    quiz.durasi_menit = saved.durasi_menit
    quiz.acak_soal = bool(saved.acak_soal)
    quiz.acak_opsi = bool(saved.acak_opsi)
    quiz.dibuka_pada = None
    quiz.ditutup_pada = None
    quiz.tampilkan_kunci = bool(saved.tampilkan_kunci)


def _konten_kuis(quiz: Quiz, questions_db: list | None = None) -> list[dict]:
    """Urutan tampil kuis: blok konten (prolog/hint/catatan) terseling soal.

    Dihitung dari teks mentah. Soal dirujuk lewat indeks urutan parse —
    atau lewat id baris questions bila `questions_db` diberikan (dipakai
    tampilan attempt yang urutan soalnya bisa diacak). Kuis format
    legacy / teks tidak valid -> daftar kosong (tampil seperti biasa).
    """
    try:
        res = parse_quiz_v2(quiz.teks_mentah or "", expected_type=quiz.tipe)
    except Exception:
        return []
    if not res["success"] or not res["content"]:
        return []
    out: list[dict] = []
    nomor = 0
    for it in res["content"].get("items") or []:
        if it.get("jenis") == "konten":
            out.append({"jenis": "konten", "tipe": it["tipe"], "teks": it["teks"]})
        else:
            if questions_db is not None and nomor < len(questions_db):
                out.append({"jenis": "soal", "question_id": questions_db[nomor].id})
            else:
                out.append({"jenis": "soal", "indeks": nomor})
            nomor += 1
    return out


def _quiz_full_out(db: Session, quiz: Quiz) -> dict:
    dokumen_materi_id = None
    if quiz.grup_dokumen:
        pasangan = (
            db.query(Material)
            .filter(Material.grup_dokumen == quiz.grup_dokumen)
            .first()
        )
        dokumen_materi_id = pasangan.id if pasangan else None
    return {
        "id": quiz.id,
        "meeting_id": quiz.meeting_id,
        "judul": quiz.judul,
        "tipe": quiz.tipe,
        "teks_mentah": quiz.teks_mentah,
        "dibuat_oleh": quiz.dibuat_oleh,
        "grup_dokumen": quiz.grup_dokumen,
        "jenis": quiz.jenis,
        "dokumen_materi_id": dokumen_materi_id,
        **quiz_settings_out(quiz),
        "questions": [question_full_out(q) for q in _questions_of(db, quiz)],
        "konten": _konten_kuis(quiz),
    }


@router.post("/api/v1/meetings/{meeting_id}/quizzes", status_code=201, dependencies=[Depends(require_csrf)])
def create_quiz(
    meeting_id: int,
    body: QuizIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = get_meeting(db, meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    parsed = _parse_or_400(body.teks_mentah, body.tipe)
    quiz = Quiz(
        meeting_id=meeting.id,
        judul=body.judul.strip(),
        tipe=body.tipe,
        teks_mentah=body.teks_mentah,
        dibuat_oleh=user.id,
    )
    _apply_settings(quiz, body)
    db.add(quiz)
    db.flush()
    _create_questions(db, quiz, parsed["questions"])
    _notify_quiz_baru(db, quiz)
    db.commit()
    db.refresh(quiz)
    return _quiz_full_out(db, quiz)


@router.post("/api/v1/meetings/{meeting_id}/quizzes/from-bank/{saved_id}", status_code=201, dependencies=[Depends(require_csrf)])
def create_quiz_from_bank(
    meeting_id: int,
    saved_id: int,
    body: Optional[QuizIn] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Buat kuis di pertemuan dari kuis bank milik user (snapshot dipakai bila ada)."""
    saved = db.get(SavedQuiz, saved_id)
    if saved is None or saved.dibuat_oleh != user.id:
        raise HTTPException(status_code=404, detail="Kuis bank tidak ditemukan.")
    meeting = get_meeting(db, meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)

    parsed = _parse_or_400(saved.teks_mentah, saved.tipe)
    quiz = Quiz(
        meeting_id=meeting.id,
        judul=(body.judul.strip() if body and body.judul else saved.judul),
        tipe=saved.tipe,
        teks_mentah=saved.teks_mentah,
        dibuat_oleh=user.id,
    )
    _apply_saved_settings(quiz, saved)
    if body is not None:
        # Field pengaturan yang EKSPLISIT dikirim pemanggil menimpa bawaan bank.
        for field in ("durasi_menit", "acak_soal", "acak_opsi", "dibuka_pada", "ditutup_pada", "tampilkan_kunci"):
            if field in body.model_fields_set:
                setattr(quiz, field, getattr(body, field))
    db.add(quiz)
    db.flush()
    _create_questions(db, quiz, parsed["questions"])
    _notify_quiz_baru(db, quiz)
    db.commit()
    db.refresh(quiz)
    return _quiz_full_out(db, quiz)


@router.get("/api/v1/quizzes/{quiz_id}")
def get_one_quiz(
    quiz_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = get_quiz(db, quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    require_subject_view(db, user, subject)
    questions = _questions_of(db, quiz)
    if user.role in ("admin", "guru") and (
        user.role == "admin" or quiz.dibuat_oleh == user.id or subject.dibuat_oleh == user.id
    ):
        return _quiz_full_out(db, quiz)

    # Tampilan siswa: tanpa kunci & tanpa teks mentah.
    my_attempt = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz.id, QuizAttempt.siswa_id == user.id)
        .first()
    )
    now = _now()
    alasan = None
    if quiz.dibuka_pada and now < _as_utc(quiz.dibuka_pada):
        alasan = f"Kuis belum dibuka. Dibuka pada {_as_utc(quiz.dibuka_pada).strftime('%d-%m-%Y %H:%M')} UTC."
    elif quiz.ditutup_pada and now > _as_utc(quiz.ditutup_pada):
        alasan = "Kuis sudah ditutup."
    elif my_attempt is not None and my_attempt.status in ("submitted", "graded"):
        alasan = "Anda sudah mengerjakan kuis ini."
    pasangan_materi = (
        db.query(Material).filter(Material.grup_dokumen == quiz.grup_dokumen).first()
        if quiz.grup_dokumen
        else None
    )
    return {
        "id": quiz.id,
        "meeting_id": quiz.meeting_id,
        "judul": quiz.judul,
        "tipe": quiz.tipe,
        "grup_dokumen": quiz.grup_dokumen,
        "jenis": quiz.jenis,
        "dokumen_materi_id": pasangan_materi.id if pasangan_materi else None,
        **quiz_settings_out(quiz),
        "jumlah_soal": len(questions),
        "total_bobot": sum(q.bobot for q in questions),
        "bisa_mulai": alasan is None,
        "alasan": alasan,
        "konten": _konten_kuis(quiz),
        "attempt_saya": (
            {
                "id": my_attempt.id,
                "status": my_attempt.status,
                "skor": my_attempt.skor,
            }
            if my_attempt is not None
            else None
        ),
    }


class QuizPatchIn(BaseModel):
    judul: Optional[str] = Field(default=None, min_length=1, max_length=200)
    teks_mentah: Optional[str] = None
    durasi_menit: Optional[int] = Field(default=None, ge=1)
    acak_soal: Optional[bool] = None
    acak_opsi: Optional[bool] = None
    dibuka_pada: Optional[datetime] = None
    ditutup_pada: Optional[datetime] = None
    tampilkan_kunci: Optional[bool] = None


@router.patch("/api/v1/quizzes/{quiz_id}", dependencies=[Depends(require_csrf)])
def update_quiz(
    quiz_id: int,
    body: QuizPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = get_quiz(db, quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    require_subject_manage(db, user, subject)

    if body.teks_mentah is not None and body.teks_mentah != quiz.teks_mentah:
        ada_attempt = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).first()
        if ada_attempt is not None:
            raise HTTPException(
                status_code=400,
                detail="Soal tidak bisa diubah: sudah ada siswa yang mengerjakan kuis ini.",
            )
        parsed = _parse_or_400(body.teks_mentah, quiz.tipe)
        for q in _questions_of(db, quiz):
            db.delete(q)
        db.flush()
        quiz.teks_mentah = body.teks_mentah
        _create_questions(db, quiz, parsed["questions"])

    if body.judul is not None:
        quiz.judul = body.judul.strip()
    # Audit #10/#32: pengaturan pengerjaan dikunci begitu ada attempt —
    # mengubah durasi/jendela/acak/tampilkan_kunci di tengah pengerjaan
    # merusak keadilan penilaian. Judul & teks (teks sudah dikunci di atas)
    # tidak termasuk.
    ada_attempt = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).first()
    for field in ("durasi_menit", "acak_soal", "acak_opsi", "dibuka_pada", "ditutup_pada", "tampilkan_kunci"):
        value = getattr(body, field)
        if value is not None:
            lama = getattr(quiz, field)
            if field in ("dibuka_pada", "ditutup_pada"):
                sama = lama is not None and _as_utc(lama) == _as_utc(value)
            else:
                sama = lama == value
            if ada_attempt is not None and not sama:
                raise HTTPException(
                    status_code=400,
                    detail="Pengaturan kuis tidak bisa diubah: sudah ada siswa yang mengerjakan kuis ini.",
                )
            setattr(quiz, field, value)
    db.commit()
    db.refresh(quiz)
    return _quiz_full_out(db, quiz)


@router.delete("/api/v1/quizzes/{quiz_id}", dependencies=[Depends(require_csrf)])
def delete_quiz(
    quiz_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = get_quiz(db, quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    require_subject_manage(db, user, subject)
    db.delete(quiz)
    db.commit()
    return {"ok": True}


class SaveToBankIn(BaseModel):
    kategori_id: Optional[int] = None


@router.post("/api/v1/quizzes/{quiz_id}/save-to-bank", status_code=201, dependencies=[Depends(require_csrf)])
def save_quiz_to_bank(
    quiz_id: int,
    body: SaveToBankIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = get_quiz(db, quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    require_subject_manage(db, user, subject)
    # Audit #40: kategori wajib milik pemanggil (dulu id kategori orang
    # lain diterima mentah-mentah di jalur ini).
    _validate_category(db, user, body.kategori_id)
    sudah = (
        db.query(SavedQuiz)
        .filter(SavedQuiz.dibuat_oleh == user.id, SavedQuiz.asal_id == quiz.id)
        .first()
    )
    if sudah is not None:
        raise HTTPException(status_code=400, detail="Kuis ini sudah ada di bank Anda.")
    parsed = parse_quiz_v2(quiz.teks_mentah, expected_type=quiz.tipe)
    snapshot = parsed["content"]["questions"] if parsed["success"] else None
    saved = SavedQuiz(
        judul=quiz.judul,
        tipe=quiz.tipe,
        # Audit #33: jenis & pasangan dokumen ikut tersimpan (dulu hilang,
        # kuis Ujian kembali dari bank sebagai Kuis biasa).
        jenis=quiz.jenis,
        grup_dokumen=quiz.grup_dokumen,
        teks_mentah=quiz.teks_mentah,
        snapshot=snapshot,
        dibuat_oleh=user.id,
        kategori_id=body.kategori_id,
        asal_id=quiz.id,
        # Audit #9: simpan pengaturan pengerjaan (jendela tidak disimpan).
        durasi_menit=quiz.durasi_menit,
        acak_soal=quiz.acak_soal,
        acak_opsi=quiz.acak_opsi,
        tampilkan_kunci=quiz.tampilkan_kunci,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {
        "id": saved.id,
        "judul": saved.judul,
        "tipe": saved.tipe,
        "kategori_id": saved.kategori_id,
        "durasi_menit": saved.durasi_menit,
        "acak_soal": saved.acak_soal,
        "acak_opsi": saved.acak_opsi,
        "tampilkan_kunci": saved.tampilkan_kunci,
    }


# ------------------------------------------------------------------- attempts
def _deadline(attempt: QuizAttempt, quiz: Quiz) -> Optional[datetime]:
    """Batas akhir attempt = yang PALING AWAL antara durasi pengerjaan dan
    jendela tutup kuis (audit #10: dulu ditutup_pada tidak pernah menjadi
    batas attempt yang sedang berjalan, jadi siswa bisa submit jauh setelah
    kuis ditutup)."""
    batas: Optional[datetime] = None
    if quiz.durasi_menit:
        batas = _as_utc(attempt.started_at) + timedelta(minutes=quiz.durasi_menit)
    if quiz.ditutup_pada:
        tutup = _as_utc(quiz.ditutup_pada)
        batas = tutup if batas is None else min(batas, tutup)
    return batas


def _answers_map(db: Session, attempt: QuizAttempt) -> dict[int, AttemptAnswer]:
    rows = db.query(AttemptAnswer).filter(AttemptAnswer.attempt_id == attempt.id).all()
    return {r.question_id: r for r in rows}


def _selected_option_ids(answer: Optional[AttemptAnswer]) -> list[int]:
    if answer is None or not answer.jawaban_teks:
        return []
    try:
        data = json.loads(answer.jawaban_teks)
        return [int(x) for x in data] if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []


def _store_answers(db: Session, attempt: QuizAttempt, questions: list[Question], payload: list) -> None:
    by_id = {q.id: q for q in questions}
    existing = _answers_map(db, attempt)
    for item in payload:
        # Audit #41: payload tak bertipe — item/id bertipe aneh dulu bisa
        # memicu 500 (AttributeError/ValueError). Lewati yang tak valid.
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id")
        if not isinstance(qid, int) or isinstance(qid, bool):
            continue
        q = by_id.get(qid)
        if q is None:
            continue
        row = existing.get(q.id)
        if row is None:
            row = AttemptAnswer(attempt_id=attempt.id, question_id=q.id)
            db.add(row)
            existing[q.id] = row
        if q.tipe == "pilihan_ganda":
            ids = item.get("option_ids") or []
            if not isinstance(ids, list):
                ids = []
            valid_ids = {o.id for o in q.options}
            bersih: list[int] = []
            for i in ids:
                if isinstance(i, bool):
                    continue
                try:
                    iv = int(i)
                except (TypeError, ValueError):
                    continue
                if iv in valid_ids and iv not in bersih:
                    bersih.append(iv)
            row.jawaban_teks = json.dumps(bersih)
            row.option_id = bersih[0] if len(bersih) == 1 else None
        else:
            teks = item.get("jawaban_teks")
            row.jawaban_teks = teks if isinstance(teks, str) else ""
    db.flush()


def _grade_and_submit(db: Session, attempt: QuizAttempt, quiz: Quiz, when: datetime) -> None:
    """Nilai PG dari jawaban tersimpan; esai menunggu penilaian guru."""
    questions = _questions_of(db, quiz)
    answers = _answers_map(db, attempt)
    total_bobot = sum(q.bobot for q in questions)
    total_poin = 0.0
    for q in questions:
        row = answers.get(q.id)
        if q.tipe == "pilihan_ganda":
            correct = {o.id for o in q.options if o.is_correct}
            selected = set(_selected_option_ids(row))
            poin = q.bobot if correct and selected == correct else 0.0
            if row is None:
                row = AttemptAnswer(attempt_id=attempt.id, question_id=q.id, jawaban_teks="[]")
                db.add(row)
            row.poin = poin
            row.is_correct = poin == q.bobot and q.bobot > 0
            total_poin += poin
    attempt.submitted_at = when
    if quiz.tipe == "pilihan_ganda":
        attempt.skor = round(100.0 * total_poin / total_bobot, 2) if total_bobot > 0 else 0.0
        attempt.status = "submitted"
    else:
        attempt.status = "submitted"  # skor menunggu penilaian esai


def _finalize_if_expired(db: Session, attempt: QuizAttempt, quiz: Quiz) -> bool:
    if attempt.status != "in_progress":
        return False
    deadline = _deadline(attempt, quiz)
    if deadline is None or _now() <= deadline:
        return False
    _grade_and_submit(db, attempt, quiz, when=deadline)
    db.commit()
    db.refresh(attempt)
    return True


def _shuffled(items: list, seed: int) -> list:
    out = list(items)
    random.Random(seed).shuffle(out)
    return out


def attempt_view(db: Session, attempt: QuizAttempt, quiz: Quiz, viewer: User) -> dict:
    questions = _questions_of(db, quiz)
    if quiz.acak_soal:
        questions = _shuffled(questions, attempt.id)
    answers = _answers_map(db, attempt)
    is_manager = viewer.role == "admin" or (
        viewer.role == "guru" and quiz.dibuat_oleh == viewer.id
    )
    submitted = attempt.status in ("submitted", "graded")
    out_questions = []
    for q in questions:
        options = list(q.options)
        if quiz.acak_opsi:
            options = _shuffled(options, attempt.id * 100000 + q.id)
        row = answers.get(q.id)
        item = {
            "id": q.id,
            "tipe": q.tipe,
            "pertanyaan": q.pertanyaan,
            "bobot": q.bobot,
            "multi": sum(1 for o in q.options if o.is_correct) > 1,
            "options": [{"id": o.id, "teks": o.teks} for o in options],
            "jawaban_option_ids": _selected_option_ids(row) if q.tipe == "pilihan_ganda" else [],
            "jawaban_teks": (row.jawaban_teks if q.tipe == "teks" else None) if row else None,
        }
        if submitted or is_manager:
            item["poin"] = row.poin if row else None
            item["is_correct"] = row.is_correct if row else None
        if is_manager or (submitted and quiz.tampilkan_kunci):
            item["kunci_option_ids"] = [o.id for o in q.options if o.is_correct]
            item["jawaban_referensi"] = q.jawaban_referensi
        out_questions.append(item)
    deadline = _deadline(attempt, quiz)
    return {
        "attempt": {
            "id": attempt.id,
            "quiz_id": quiz.id,
            "siswa_id": attempt.siswa_id,
            "status": attempt.status,
            "skor": attempt.skor,
            "started_at": _as_utc(attempt.started_at).isoformat() if attempt.started_at else None,
            "submitted_at": _as_utc(attempt.submitted_at).isoformat() if attempt.submitted_at else None,
            "deadline": deadline.isoformat() if deadline else None,
        },
        "quiz": {"id": quiz.id, "judul": quiz.judul, "tipe": quiz.tipe, **quiz_settings_out(quiz)},
        "questions": out_questions,
        "konten": _konten_kuis(quiz, _questions_of(db, quiz)),
    }


def _get_attempt(db: Session, attempt_id: int) -> QuizAttempt:
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt tidak ditemukan.")
    return attempt


def _require_attempt_access(db: Session, attempt: QuizAttempt, user: User) -> Quiz:
    quiz = get_quiz(db, attempt.quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    if user.id == attempt.siswa_id:
        # Audit #11: kepemilikan attempt saja tidak cukup — siswa yang sudah
        # dikeluarkan dari kelas kehilangan akses baca/simpan/submit, sama
        # seperti akses materi & Cek Pemahaman.
        require_subject_view(db, user, subject)
        return quiz
    require_subject_manage(db, user, subject)
    return quiz


@router.post("/api/v1/quizzes/{quiz_id}/attempts", status_code=201, dependencies=[Depends(require_csrf)])
def start_attempt(
    quiz_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = get_quiz(db, quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    if user.role != "siswa":
        raise HTTPException(status_code=403, detail="Hanya siswa yang mengerjakan kuis.")
    require_subject_view(db, user, subject)

    existing = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz.id, QuizAttempt.siswa_id == user.id)
        .first()
    )
    if existing is not None:
        if existing.status in ("submitted", "graded"):
            raise HTTPException(status_code=400, detail="Anda sudah mengerjakan kuis ini.")
        _finalize_if_expired(db, existing, quiz)
        if existing.status != "in_progress":
            raise HTTPException(status_code=400, detail="Waktu pengerjaan sudah habis; attempt ditutup otomatis.")
        return attempt_view(db, existing, quiz, user)  # resume

    now = _now()
    if quiz.dibuka_pada and now < _as_utc(quiz.dibuka_pada):
        raise HTTPException(status_code=400, detail="Kuis belum dibuka.")
    if quiz.ditutup_pada and now > _as_utc(quiz.ditutup_pada):
        raise HTTPException(status_code=400, detail="Kuis sudah ditutup.")

    attempt = QuizAttempt(quiz_id=quiz.id, siswa_id=user.id, status="in_progress")
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        # Audit #29: request bersamaan dari siswa yang sama — indeks unik
        # parsial menolak attempt aktif kedua; lanjutkan attempt yang menang.
        db.rollback()
        existing = (
            db.query(QuizAttempt)
            .filter(
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.siswa_id == user.id,
                QuizAttempt.status == "in_progress",
            )
            .first()
        )
        if existing is None:
            raise HTTPException(status_code=409, detail="Attempt sedang dibuat — coba lagi sebentar.")
        return attempt_view(db, existing, quiz, user)
    db.refresh(attempt)
    return attempt_view(db, attempt, quiz, user)


@router.get("/api/v1/attempts/{attempt_id}")
def get_attempt(
    attempt_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt(db, attempt_id)
    quiz = _require_attempt_access(db, attempt, user)
    if user.id == attempt.siswa_id:
        _finalize_if_expired(db, attempt, quiz)
    return attempt_view(db, attempt, quiz, user)


class AnswersIn(BaseModel):
    answers: list[dict]


@router.put("/api/v1/attempts/{attempt_id}/answers", dependencies=[Depends(require_csrf)])
def save_answers(
    attempt_id: int,
    body: AnswersIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt(db, attempt_id)
    if attempt.siswa_id != user.id:
        raise HTTPException(status_code=403, detail="Attempt ini bukan milik Anda.")
    quiz = _require_attempt_access(db, attempt, user)  # audit #11: enrollment dicek
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt sudah ditutup.")
    if _finalize_if_expired(db, attempt, quiz):
        raise HTTPException(status_code=400, detail="Waktu pengerjaan sudah habis; attempt ditutup otomatis.")
    _store_answers(db, attempt, _questions_of(db, quiz), body.answers)
    db.commit()
    return {"ok": True, "pesan": "Jawaban tersimpan sebagai draf."}


@router.post("/api/v1/attempts/{attempt_id}/submit", dependencies=[Depends(require_csrf)])
def submit_attempt(
    attempt_id: int,
    body: Optional[AnswersIn] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt(db, attempt_id)
    if attempt.siswa_id != user.id:
        raise HTTPException(status_code=403, detail="Attempt ini bukan milik Anda.")
    quiz = _require_attempt_access(db, attempt, user)  # audit #11: enrollment dicek
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt sudah ditutup.")
    deadline = _deadline(attempt, quiz)
    if deadline is not None and _now() > deadline + timedelta(seconds=GRACE_SECONDS):
        _finalize_if_expired(db, attempt, quiz)
        return {
            **attempt_view(db, attempt, quiz, user),
            "pesan": "Waktu habis — attempt ditutup otomatis dengan jawaban terakhir yang tersimpan.",
        }
    if body is not None and body.answers:
        _store_answers(db, attempt, _questions_of(db, quiz), body.answers)
    _grade_and_submit(db, attempt, quiz, when=_now())
    db.commit()
    db.refresh(attempt)
    if quiz.tipe == "teks":
        subject, _ = _subject_of_quiz(db, quiz)
        notify(
            db,
            [subject.dibuat_oleh],
            "attempt_masuk",
            {"quiz_id": quiz.id, "attempt_id": attempt.id, "judul": quiz.judul, "siswa_id": user.id},
        )
        db.commit()
    return attempt_view(db, attempt, quiz, user)


# ------------------------------------------------------------- hasil & nilai
@router.get("/api/v1/quizzes/{quiz_id}/results")
def quiz_results(
    quiz_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = get_quiz(db, quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    require_subject_manage(db, user, subject)
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz.id)
        .order_by(QuizAttempt.started_at)
        .all()
    )
    out = []
    for a in attempts:
        siswa = db.get(User, a.siswa_id)
        out.append(
            {
                "attempt_id": a.id,
                "siswa": {
                    "id": siswa.id,
                    "username": siswa.username,
                    "nama_lengkap": siswa.nama_lengkap,
                }
                if siswa
                else None,
                "status": a.status,
                "skor": a.skor,
                "started_at": _as_utc(a.started_at).isoformat() if a.started_at else None,
                "submitted_at": _as_utc(a.submitted_at).isoformat() if a.submitted_at else None,
            }
        )
    return out


class GradeIn(BaseModel):
    grades: list[dict]  # [{question_id, poin}]


@router.post("/api/v1/attempts/{attempt_id}/grade", dependencies=[Depends(require_csrf)])
def grade_attempt(
    attempt_id: int,
    body: GradeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt(db, attempt_id)
    quiz = get_quiz(db, attempt.quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    require_subject_manage(db, user, subject)
    if attempt.status == "in_progress":
        raise HTTPException(status_code=400, detail="Attempt belum disubmit siswa.")

    questions = _questions_of(db, quiz)
    by_id = {q.id: q for q in questions}
    answers = _answers_map(db, attempt)
    for g in body.grades:
        q = by_id.get(g.get("question_id"))
        if q is None:
            continue
        poin = float(g.get("poin"))
        if poin < 0 or poin > q.bobot + 1e-9:
            raise HTTPException(
                status_code=400,
                detail=f"Poin soal harus antara 0 dan bobot soal ({q.bobot}).",
            )
        row = answers.get(q.id)
        if row is None:
            row = AttemptAnswer(attempt_id=attempt.id, question_id=q.id, jawaban_teks="")
            db.add(row)
            answers[q.id] = row
        row.poin = poin
        row.is_correct = poin >= q.bobot

    if all(answers.get(q.id) is not None and answers[q.id].poin is not None for q in questions):
        total_bobot = sum(q.bobot for q in questions)
        total_poin = sum(answers[q.id].poin or 0 for q in questions)
        attempt.skor = round(100.0 * total_poin / total_bobot, 2) if total_bobot > 0 else 0.0
        attempt.status = "graded"
    db.commit()
    db.refresh(attempt)
    if attempt.status == "graded":
        notify(
            db,
            [attempt.siswa_id],
            "nilai_keluar",
            {"quiz_id": quiz.id, "attempt_id": attempt.id, "judul": quiz.judul, "skor": attempt.skor},
        )
        db.commit()
    return attempt_view(db, attempt, quiz, user)


@router.get("/api/v1/quizzes/{quiz_id}/export")
def export_results(
    quiz_id: int,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response

    quiz = get_quiz(db, quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    require_subject_manage(db, user, subject)
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz.id)
        .order_by(QuizAttempt.started_at)
        .all()
    )
    header = ["Username", "Nama Lengkap", "Status", "Skor", "Mulai", "Submit"]
    rows = []
    for a in attempts:
        siswa = db.get(User, a.siswa_id)
        rows.append(
            [
                siswa.username if siswa else "",
                (siswa.nama_lengkap or "") if siswa else "",
                a.status,
                "" if a.skor is None else a.skor,
                _as_utc(a.started_at).strftime("%Y-%m-%d %H:%M") if a.started_at else "",
                _as_utc(a.submitted_at).strftime("%Y-%m-%d %H:%M") if a.submitted_at else "",
            ]
        )
    filename = f"nilai-kuis-{quiz.id}"
    if format == "csv":
        import csv

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        writer.writerows(rows)
        return Response(
            content="﻿" + buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Nilai Kuis"
    ws.append(header)
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return Response(
        content=bio.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )


# ------------------------------------------------------- bank soal (Fase 4)
def questions_to_tcml(tipe: str, questions: list[dict]) -> str:
    """Bangun teks TCML kanonis dari data soal ternormalisasi.

    Hasilnya harus selalu lolos parse_quiz_v2 — kuis hasil susunan dari bank
    soal tetap punya teks mentah yang bisa diedit guru di editor TCML.
    """
    lines = ["[QUIZ]", f"[TYPE]{'pilihan_ganda' if tipe == 'pilihan_ganda' else 'essay'}[/TYPE]"]
    for i, q in enumerate(questions, start=1):
        lines.append(f"[QUESTION {i}]")
        lines.append(f"[QUESTION]{q['pertanyaan']}[/QUESTION]")
        if tipe == "pilihan_ganda":
            lines.append("[OPTIONS]")
            for o in q.get("options", []):
                lines.append(f"{o['label']}. {o['teks']}")
            lines.append("[/OPTIONS]")
            kunci = ", ".join(o["label"] for o in q.get("options", []) if o["is_correct"])
            lines.append(f"[ANSWER]{kunci}[/ANSWER]")
        elif q.get("jawaban_referensi"):
            lines.append(f"[ANSWER]{q['jawaban_referensi']}[/ANSWER]")
        if q.get("bobot", 1) not in (1, 1.0):
            bobot = q["bobot"]
            lines.append(f"[WEIGHT]{int(bobot) if float(bobot).is_integer() else bobot}[/WEIGHT]")
        lines.append(f"[/QUESTION {i}]")
    lines.append("[/QUIZ]")
    return "\n".join(lines)


class ExtractIn(BaseModel):
    kategori_id: Optional[int] = None


@router.post("/api/v1/quizzes/{quiz_id}/extract-questions", status_code=201, dependencies=[Depends(require_csrf)])
def extract_questions(
    quiz_id: int,
    body: ExtractIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simpan semua soal kuis ini ke bank soal milik guru."""
    quiz = get_quiz(db, quiz_id)
    subject, _ = _subject_of_quiz(db, quiz)
    require_subject_manage(db, user, subject)
    _validate_category(db, user, body.kategori_id)
    created = 0
    for q in _questions_of(db, quiz):
        db.add(
            BankQuestion(
                dibuat_oleh=user.id,
                kategori_id=body.kategori_id,
                tipe=q.tipe,
                pertanyaan=q.pertanyaan,
                bobot=q.bobot,
                options=(
                    [
                        {"label": o.label, "teks": o.teks, "is_correct": o.is_correct}
                        for o in q.options
                    ]
                    if q.tipe == "pilihan_ganda"
                    else None
                ),
                jawaban_referensi=q.jawaban_referensi if q.tipe == "teks" else None,
            )
        )
        created += 1
    db.commit()
    return {"ok": True, "jumlah_diekstrak": created}


class ComposeIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    jumlah: int = Field(ge=1)
    kategori_id: Optional[int] = None
    tipe: str = Field(default="pilihan_ganda", pattern="^(pilihan_ganda|teks)$")
    durasi_menit: Optional[int] = Field(default=None, ge=1)
    acak_soal: bool = False
    acak_opsi: bool = False
    dibuka_pada: Optional[datetime] = None
    ditutup_pada: Optional[datetime] = None
    tampilkan_kunci: bool = True


@router.post("/api/v1/meetings/{meeting_id}/quizzes/from-bank-questions", status_code=201, dependencies=[Depends(require_csrf)])
def compose_quiz_from_bank_questions(
    meeting_id: int,
    body: ComposeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Susun kuis baru dengan menarik `jumlah` soal acak dari bank soal guru."""
    meeting = get_meeting(db, meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    if body.kategori_id is not None:
        _validate_category(db, user, body.kategori_id)

    pool_q = db.query(BankQuestion).filter(
        BankQuestion.dibuat_oleh == user.id,
        BankQuestion.tipe == body.tipe,
    )
    if body.kategori_id is not None:
        pool_q = pool_q.filter(BankQuestion.kategori_id == body.kategori_id)
    pool = pool_q.all()
    if body.jumlah > len(pool):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Soal di bank tidak cukup: diminta {body.jumlah}, tersedia {len(pool)} "
                f"(tipe {body.tipe}{' pada kategori ini' if body.kategori_id else ''})."
            ),
        )
    drawn = random.sample(pool, body.jumlah)
    data = [
        {
            "tipe": r.tipe,
            "pertanyaan": r.pertanyaan,
            "bobot": r.bobot,
            "options": r.options or [],
            "jawaban_referensi": r.jawaban_referensi,
        }
        for r in drawn
    ]
    # Audit #37: teks kanonis hasil susunan WAJIB parse kembali menjadi
    # soal yang sama persis. Teks soal bank yang mengandung baris/tag
    # penutup TCML bisa mengubah makna saat direpresentasikan — dulu lolos
    # diam-diam dan kuis terbit dengan isi berbeda dari bank.
    teks_kanonis = questions_to_tcml(body.tipe, data)
    cek = parse_quiz_v2(teks_kanonis, expected_type=body.tipe)
    if not cek["success"]:
        raise HTTPException(
            status_code=400,
            detail="Sebagian soal bank tidak bisa disusun menjadi kuis TCML yang valid (kemungkinan teksnya mengandung tag penutup TCML). Perbaiki teks soal di bank terlebih dahulu.",
        )
    hasil = cek["content"]["questions"]
    sama = len(hasil) == len(data) and all(
        h["pertanyaan"] == d["pertanyaan"]
        and [o["teks"] for o in h["options"]] == [o["teks"] for o in d["options"]]
        and (h["jawaban_referensi"] or None) == (d["jawaban_referensi"] or None)
        for h, d in zip(hasil, data)
    )
    if not sama:
        raise HTTPException(
            status_code=400,
            detail="Sebagian soal bank berubah makna saat disusun menjadi TCML (kemungkinan teksnya mengandung tag TCML). Perbaiki teks soal di bank terlebih dahulu.",
        )
    quiz = Quiz(
        meeting_id=meeting.id,
        judul=body.judul.strip(),
        tipe=body.tipe,
        teks_mentah=teks_kanonis,
        dibuat_oleh=user.id,
        durasi_menit=body.durasi_menit,
        acak_soal=body.acak_soal,
        acak_opsi=body.acak_opsi,
        dibuka_pada=body.dibuka_pada,
        ditutup_pada=body.ditutup_pada,
        tampilkan_kunci=body.tampilkan_kunci,
    )
    db.add(quiz)
    db.flush()
    _create_questions(db, quiz, data)
    _notify_quiz_baru(db, quiz)
    db.commit()
    db.refresh(quiz)
    return _quiz_full_out(db, quiz)
