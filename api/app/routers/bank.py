"""Router Bank Materi & Kuis (Fase 2).

Bank bersifat personal per guru/admin (dibuat_oleh = pemilik). Materi bank
bisa dipakai ke pertemuan mana pun milik pemilik lewat
POST /api/v1/meetings/{id}/materials/from-bank/{saved_id} (di materials.py).
Kuis bank menyimpan snapshot struktur soal hasil parse; penempatan kuis
bank ke pertemuan dilakukan Fase 3 bersama modul kuis.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_csrf, require_roles
from ..models import BankQuestion, SavedCategory, SavedMaterial, SavedQuiz, User
from ..tcml import parse_material
from ..tcml.quiz import parse_quiz_v2

router = APIRouter(prefix="/api/v1/bank", tags=["bank"])
staff = require_roles("guru", "admin")


# ---------------------------------------------------------------- categories
class CategoryIn(BaseModel):
    nama: str = Field(min_length=1, max_length=100)


def _own_category(db: Session, user: User, category_id: int) -> SavedCategory:
    c = db.get(SavedCategory, category_id)
    if c is None or c.dibuat_oleh != user.id:
        raise HTTPException(status_code=404, detail="Kategori tidak ditemukan.")
    return c


@router.get("/categories")
def list_categories(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = (
        db.query(SavedCategory)
        .filter(SavedCategory.dibuat_oleh == user.id)
        .order_by(SavedCategory.nama)
        .all()
    )
    return [{"id": c.id, "nama": c.nama} for c in rows]


@router.post("/categories", status_code=201, dependencies=[Depends(require_csrf)])
def create_category(body: CategoryIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = SavedCategory(nama=body.nama.strip(), dibuat_oleh=user.id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "nama": c.nama}


@router.delete("/categories/{category_id}", dependencies=[Depends(require_csrf)])
def delete_category(category_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = _own_category(db, user, category_id)
    db.query(SavedMaterial).filter(SavedMaterial.kategori_id == c.id).update(
        {SavedMaterial.kategori_id: None}, synchronize_session=False
    )
    db.query(SavedQuiz).filter(SavedQuiz.kategori_id == c.id).update(
        {SavedQuiz.kategori_id: None}, synchronize_session=False
    )
    db.query(BankQuestion).filter(BankQuestion.kategori_id == c.id).update(
        {BankQuestion.kategori_id: None}, synchronize_session=False
    )
    db.delete(c)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------ saved materials
class SavedMaterialIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    teks_mentah: str = Field(min_length=1)
    kategori_id: Optional[int] = None


def saved_material_out(s: SavedMaterial) -> dict:
    return {
        "id": s.id,
        "judul": s.judul,
        "teks_mentah": s.teks_mentah,
        "kategori_id": s.kategori_id,
    }


def _own_saved_material(db: Session, user: User, saved_id: int) -> SavedMaterial:
    s = db.get(SavedMaterial, saved_id)
    if s is None or s.dibuat_oleh != user.id:
        raise HTTPException(status_code=404, detail="Materi bank tidak ditemukan.")
    return s


def _validate_category(db: Session, user: User, kategori_id: Optional[int]) -> None:
    if kategori_id is not None:
        _own_category(db, user, kategori_id)


@router.get("/materials")
def list_saved_materials(
    kategori_id: Optional[int] = Query(default=None),
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    q = db.query(SavedMaterial).filter(SavedMaterial.dibuat_oleh == user.id)
    if kategori_id is not None:
        q = q.filter(SavedMaterial.kategori_id == kategori_id)
    return [saved_material_out(s) for s in q.order_by(SavedMaterial.judul).all()]


@router.post("/materials", status_code=201, dependencies=[Depends(require_csrf)])
def create_saved_material(body: SavedMaterialIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    res = parse_material(body.teks_mentah)
    if not res["success"]:
        raise HTTPException(status_code=400, detail={"pesan": "Teks TCML tidak valid.", "errors": res["errors"]})
    _validate_category(db, user, body.kategori_id)
    s = SavedMaterial(
        judul=body.judul.strip(),
        teks_mentah=body.teks_mentah,
        dibuat_oleh=user.id,
        kategori_id=body.kategori_id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return saved_material_out(s)


@router.get("/materials/{saved_id}")
def get_saved_material(saved_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    return saved_material_out(_own_saved_material(db, user, saved_id))


@router.patch("/materials/{saved_id}", dependencies=[Depends(require_csrf)])
def update_saved_material(
    saved_id: int,
    body: SavedMaterialIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    s = _own_saved_material(db, user, saved_id)
    res = parse_material(body.teks_mentah)
    if not res["success"]:
        raise HTTPException(status_code=400, detail={"pesan": "Teks TCML tidak valid.", "errors": res["errors"]})
    _validate_category(db, user, body.kategori_id)
    s.judul = body.judul.strip()
    s.teks_mentah = body.teks_mentah
    s.kategori_id = body.kategori_id
    db.commit()
    db.refresh(s)
    return saved_material_out(s)


@router.delete("/materials/{saved_id}", dependencies=[Depends(require_csrf)])
def delete_saved_material(saved_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = _own_saved_material(db, user, saved_id)
    db.delete(s)
    db.commit()
    return {"ok": True}


# -------------------------------------------------------------- saved quizzes
class SavedQuizIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    tipe: str = Field(pattern="^(pilihan_ganda|teks)$")
    teks_mentah: str = Field(min_length=1)
    kategori_id: Optional[int] = None


def saved_quiz_out(s: SavedQuiz) -> dict:
    return {
        "id": s.id,
        "judul": s.judul,
        "tipe": s.tipe,
        "teks_mentah": s.teks_mentah,
        "kategori_id": s.kategori_id,
        "jumlah_soal": len(s.snapshot) if isinstance(s.snapshot, list) else 0,
    }


@router.get("/quizzes")
def list_saved_quizzes(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = (
        db.query(SavedQuiz)
        .filter(SavedQuiz.dibuat_oleh == user.id)
        .order_by(SavedQuiz.judul)
        .all()
    )
    return [saved_quiz_out(s) for s in rows]


@router.post("/quizzes", status_code=201, dependencies=[Depends(require_csrf)])
def create_saved_quiz(body: SavedQuizIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    # Validasi & snapshot memakai parser kuis v2 (mendukung [WEIGHT] & multi-jawaban).
    res = parse_quiz_v2(body.teks_mentah, expected_type=body.tipe)
    if not res["success"]:
        raise HTTPException(status_code=400, detail={"pesan": "Teks TCML kuis tidak valid.", "errors": res["errors"]})
    _validate_category(db, user, body.kategori_id)
    s = SavedQuiz(
        judul=body.judul.strip(),
        tipe=body.tipe,
        teks_mentah=body.teks_mentah,
        snapshot=res["content"]["questions"],
        dibuat_oleh=user.id,
        kategori_id=body.kategori_id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return saved_quiz_out(s)


@router.delete("/quizzes/{saved_id}", dependencies=[Depends(require_csrf)])
def delete_saved_quiz(saved_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = db.get(SavedQuiz, saved_id)
    if s is None or s.dibuat_oleh != user.id:
        raise HTTPException(status_code=404, detail="Kuis bank tidak ditemukan.")
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/quizzes/{saved_id}/extract-questions", status_code=201, dependencies=[Depends(require_csrf)])
def extract_saved_quiz_questions(
    saved_id: int,
    kategori_id: Optional[int] = None,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    """Masukkan semua soal kuis bank ini ke bank soal pemiliknya (permintaan
    Qualze, paket 2026-10-20). Soal yang persis sama dengan yang sudah ada
    di bank soal dilewati, tidak digandakan. Kategori tujuan: parameter
    ?kategori_id= bila dipilih, kalau tidak mengikuti kategori kuis bank."""
    import json as _json

    s = db.get(SavedQuiz, saved_id)
    if s is None or s.dibuat_oleh != user.id:
        raise HTTPException(status_code=404, detail="Kuis bank tidak ditemukan.")
    kategori_tujuan = s.kategori_id
    if kategori_id is not None:
        _validate_category(db, user, kategori_id)
        kategori_tujuan = kategori_id
    questions = s.snapshot if isinstance(s.snapshot, list) else None
    if questions is None:
        from ..tcml import parse_quiz_v2

        parsed = parse_quiz_v2(s.teks_mentah, expected_type=s.tipe)
        if not parsed["success"]:
            raise HTTPException(status_code=400, detail="Teks kuis bank tidak valid sehingga tidak bisa diekstrak.")
        questions = parsed["content"]["questions"]

    def kunci(tipe: str, pertanyaan: str, options) -> str:
        opsi = _json.dumps(options or [], sort_keys=True, ensure_ascii=False)
        return f"{tipe}|{pertanyaan.strip()}|{opsi}"

    sudah_ada = {
        kunci(q.tipe, q.pertanyaan, q.options)
        for q in db.query(BankQuestion).filter(BankQuestion.dibuat_oleh == user.id)
    }
    dimasukkan, dilewati = 0, 0
    for q in questions:
        options = q.get("options") if s.tipe == "pilihan_ganda" else None
        k = kunci(s.tipe, q.get("pertanyaan", ""), options)
        if k in sudah_ada:
            dilewati += 1
            continue
        sudah_ada.add(k)
        db.add(
            BankQuestion(
                dibuat_oleh=user.id,
                kategori_id=kategori_tujuan,
                tipe=s.tipe,
                pertanyaan=q.get("pertanyaan", ""),
                bobot=q.get("bobot", 1.0),
                options=options,
                jawaban_referensi=q.get("jawaban_referensi") if s.tipe == "teks" else None,
            )
        )
        dimasukkan += 1
    db.commit()
    return {"ok": True, "dimasukkan": dimasukkan, "dilewati": dilewati}


# ------------------------------------------- jelajahi & salin bank guru lain
def _owner_info(db: Session, user_id: int) -> dict:
    u = db.get(User, user_id)
    if u is None:
        return {"id": user_id, "username": "?", "nama_lengkap": None}
    return {"id": u.id, "username": u.username, "nama_lengkap": u.nama_lengkap}


@router.get("/explore/materials")
def explore_materials(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = (
        db.query(SavedMaterial)
        .filter(SavedMaterial.dibuat_oleh != user.id)
        .order_by(SavedMaterial.judul)
        .all()
    )
    return [{**saved_material_out(s), "pemilik": _owner_info(db, s.dibuat_oleh)} for s in rows]


@router.get("/explore/quizzes")
def explore_quizzes(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = (
        db.query(SavedQuiz)
        .filter(SavedQuiz.dibuat_oleh != user.id)
        .order_by(SavedQuiz.judul)
        .all()
    )
    return [{**saved_quiz_out(s), "pemilik": _owner_info(db, s.dibuat_oleh)} for s in rows]


@router.post("/materials/{saved_id}/copy", status_code=201, dependencies=[Depends(require_csrf)])
def copy_saved_material(saved_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    src = db.get(SavedMaterial, saved_id)
    if src is None:
        raise HTTPException(status_code=404, detail="Materi bank tidak ditemukan.")
    s = SavedMaterial(
        judul=src.judul,
        teks_mentah=src.teks_mentah,
        dibuat_oleh=user.id,
        kategori_id=None,  # kategori bersifat personal; salinan mulai tanpa kategori
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return saved_material_out(s)


@router.post("/quizzes/{saved_id}/copy", status_code=201, dependencies=[Depends(require_csrf)])
def copy_saved_quiz(saved_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    src = db.get(SavedQuiz, saved_id)
    if src is None:
        raise HTTPException(status_code=404, detail="Kuis bank tidak ditemukan.")
    s = SavedQuiz(
        judul=src.judul,
        tipe=src.tipe,
        teks_mentah=src.teks_mentah,
        snapshot=list(src.snapshot) if isinstance(src.snapshot, list) else src.snapshot,
        dibuat_oleh=user.id,
        kategori_id=None,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return saved_quiz_out(s)


# ----------------------------------------------------------------- bank soal
class BankQuestionIn(BaseModel):
    tipe: str = Field(pattern="^(pilihan_ganda|teks)$")
    pertanyaan: str = Field(min_length=1)
    bobot: float = Field(default=1.0, gt=0)
    options: Optional[list] = None  # [{label, teks, is_correct}] untuk PG
    jawaban_referensi: Optional[str] = None
    kategori_id: Optional[int] = None


def bank_question_out(q: BankQuestion) -> dict:
    return {
        "id": q.id,
        "tipe": q.tipe,
        "pertanyaan": q.pertanyaan,
        "bobot": q.bobot,
        "options": q.options,
        "jawaban_referensi": q.jawaban_referensi,
        "kategori_id": q.kategori_id,
    }


def _validate_bank_question(body: BankQuestionIn) -> list:
    """Normalisasi & validasi opsi PG; kembalikan daftar opsi bersih."""
    if body.tipe == "teks":
        return []
    options = body.options or []
    cleaned = []
    seen_labels = set()
    for o in options:
        label = str(o.get("label", "")).strip().upper()
        teks = str(o.get("teks", "")).strip()
        if not label or not teks:
            continue
        if label in seen_labels:
            raise HTTPException(status_code=400, detail=f"Label opsi duplikat: {label}.")
        seen_labels.add(label)
        cleaned.append({"label": label, "teks": teks, "is_correct": bool(o.get("is_correct"))})
    if len(cleaned) < 2:
        raise HTTPException(status_code=400, detail="Soal pilihan ganda butuh minimal 2 opsi.")
    if not any(o["is_correct"] for o in cleaned):
        raise HTTPException(status_code=400, detail="Soal pilihan ganda butuh minimal 1 jawaban benar.")
    return cleaned


def _own_bank_question(db: Session, user: User, qid: int) -> BankQuestion:
    q = db.get(BankQuestion, qid)
    if q is None or q.dibuat_oleh != user.id:
        raise HTTPException(status_code=404, detail="Soal bank tidak ditemukan.")
    return q


@router.get("/questions")
def list_bank_questions(
    kategori_id: Optional[int] = Query(default=None),
    tipe: Optional[str] = Query(default=None),
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    q = db.query(BankQuestion).filter(BankQuestion.dibuat_oleh == user.id)
    if kategori_id is not None:
        q = q.filter(BankQuestion.kategori_id == kategori_id)
    if tipe is not None:
        q = q.filter(BankQuestion.tipe == tipe)
    return [bank_question_out(x) for x in q.order_by(BankQuestion.id).all()]


@router.post("/questions", status_code=201, dependencies=[Depends(require_csrf)])
def create_bank_question(body: BankQuestionIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    options = _validate_bank_question(body)
    _validate_category(db, user, body.kategori_id)
    q = BankQuestion(
        dibuat_oleh=user.id,
        kategori_id=body.kategori_id,
        tipe=body.tipe,
        pertanyaan=body.pertanyaan.strip(),
        bobot=body.bobot,
        options=options if body.tipe == "pilihan_ganda" else None,
        jawaban_referensi=body.jawaban_referensi if body.tipe == "teks" else None,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return bank_question_out(q)


@router.patch("/questions/{question_id}", dependencies=[Depends(require_csrf)])
def update_bank_question(
    question_id: int,
    body: BankQuestionIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    q = _own_bank_question(db, user, question_id)
    options = _validate_bank_question(body)
    _validate_category(db, user, body.kategori_id)
    q.tipe = body.tipe
    q.pertanyaan = body.pertanyaan.strip()
    q.bobot = body.bobot
    q.options = options if body.tipe == "pilihan_ganda" else None
    q.jawaban_referensi = body.jawaban_referensi if body.tipe == "teks" else None
    q.kategori_id = body.kategori_id
    db.commit()
    db.refresh(q)
    return bank_question_out(q)


@router.delete("/questions/{question_id}", dependencies=[Depends(require_csrf)])
def delete_bank_question(question_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    q = _own_bank_question(db, user, question_id)
    db.delete(q)
    db.commit()
    return {"ok": True}
