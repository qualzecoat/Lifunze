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
from ..models import SavedCategory, SavedMaterial, SavedQuiz, User
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
