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
        "grup_dokumen": s.grup_dokumen,
        "jenis": s.jenis,
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
        "grup_dokumen": s.grup_dokumen,
        "jenis": s.jenis,
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


# ------------------------------------------------------- dokumen bank terpadu
class BankDocumentIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    jenis: str = Field(pattern="^(materi|tugas|kuis|ujian)$")
    kategori_id: Optional[int] = None
    teks_materi: Optional[str] = None
    teks_kuis_pg: Optional[str] = None
    teks_kuis_esai: Optional[str] = None


class BankDocUseIn(BaseModel):
    meeting_id: int


def _bank_doc_parts(db: Session, user: User, grup: str, milik_sendiri: bool = True):
    qm = db.query(SavedMaterial).filter(SavedMaterial.grup_dokumen == grup)
    qq = db.query(SavedQuiz).filter(SavedQuiz.grup_dokumen == grup)
    if milik_sendiri:
        qm = qm.filter(SavedMaterial.dibuat_oleh == user.id)
        qq = qq.filter(SavedQuiz.dibuat_oleh == user.id)
    material = qm.first()
    quizzes = qq.order_by(SavedQuiz.id).all()
    return material, quizzes


def _bank_document_out(material, quizzes, grup: str) -> dict:
    anchor = material or (quizzes[0] if quizzes else None)
    if anchor is None:
        raise HTTPException(status_code=404, detail="Dokumen bank tidak ditemukan.")
    return {
        "grup": grup,
        "judul": anchor.judul,
        "jenis": anchor.jenis,
        "kategori_id": anchor.kategori_id,
        "material": saved_material_out(material) if material else None,
        "quizzes": [saved_quiz_out(s) for s in quizzes],
    }


def _snapshot_kuis(teks: str, tipe: str) -> list:
    res = parse_quiz_v2(teks, expected_type=tipe)
    if not res["success"]:
        raise HTTPException(
            status_code=400,
            detail={"pesan": "Teks TCML kuis tidak valid.", "errors": res["errors"]},
        )
    return res["content"]["questions"]


@router.post("/documents", status_code=201, dependencies=[Depends(require_csrf)])
def create_bank_document(body: BankDocumentIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    import uuid

    if not any((t or "").strip() for t in (body.teks_materi, body.teks_kuis_pg, body.teks_kuis_esai)):
        raise HTTPException(status_code=400, detail="Dokumen kosong — isi bagian materi atau kuis dulu.")
    _validate_category(db, user, body.kategori_id)
    grup = uuid.uuid4().hex
    material = None
    if (body.teks_materi or "").strip():
        res = parse_material(body.teks_materi)
        if not res["success"]:
            raise HTTPException(status_code=400, detail={"pesan": "Bagian materi tidak valid.", "errors": res["errors"]})
        material = SavedMaterial(
            judul=body.judul.strip(), teks_mentah=body.teks_materi,
            dibuat_oleh=user.id, kategori_id=body.kategori_id,
            grup_dokumen=grup, jenis=body.jenis,
        )
        db.add(material)
    quizzes = []
    for tipe, teks in (("pilihan_ganda", body.teks_kuis_pg), ("teks", body.teks_kuis_esai)):
        if (teks or "").strip():
            s = SavedQuiz(
                judul=body.judul.strip(), tipe=tipe, teks_mentah=teks,
                snapshot=_snapshot_kuis(teks, tipe),
                dibuat_oleh=user.id, kategori_id=body.kategori_id,
                grup_dokumen=grup, jenis=body.jenis,
            )
            db.add(s)
            quizzes.append(s)
    db.commit()
    if material is not None:
        db.refresh(material)
    for s in quizzes:
        db.refresh(s)
    return _bank_document_out(material, quizzes, grup)


@router.get("/documents/{grup}")
def get_bank_document(grup: str, user: User = Depends(staff), db: Session = Depends(get_db)):
    material, quizzes = _bank_doc_parts(db, user, grup)
    return _bank_document_out(material, quizzes, grup)


@router.patch("/documents/{grup}", dependencies=[Depends(require_csrf)])
def update_bank_document(grup: str, body: BankDocumentIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    material, quizzes = _bank_doc_parts(db, user, grup)
    _bank_document_out(material, quizzes, grup)  # 404 bila bukan dokumen milik user
    if not any((t or "").strip() for t in (body.teks_materi, body.teks_kuis_pg, body.teks_kuis_esai)):
        raise HTTPException(status_code=400, detail="Dokumen tidak boleh kosong.")
    _validate_category(db, user, body.kategori_id)

    if (body.teks_materi or "").strip():
        res = parse_material(body.teks_materi)
        if not res["success"]:
            raise HTTPException(status_code=400, detail={"pesan": "Bagian materi tidak valid.", "errors": res["errors"]})
        if material is None:
            material = SavedMaterial(dibuat_oleh=user.id, grup_dokumen=grup, judul=body.judul.strip(), teks_mentah=body.teks_materi)
            db.add(material)
        material.judul = body.judul.strip()
        material.teks_mentah = body.teks_materi
        material.jenis = body.jenis
        material.kategori_id = body.kategori_id
    elif material is not None:
        db.delete(material)
        material = None

    by_tipe = {s.tipe: s for s in quizzes}
    sisa = []
    for tipe, teks in (("pilihan_ganda", body.teks_kuis_pg), ("teks", body.teks_kuis_esai)):
        existing = by_tipe.get(tipe)
        if (teks or "").strip():
            snap = _snapshot_kuis(teks, tipe)
            if existing is None:
                existing = SavedQuiz(dibuat_oleh=user.id, grup_dokumen=grup, tipe=tipe, judul=body.judul.strip(), teks_mentah=teks, snapshot=snap)
                db.add(existing)
            existing.judul = body.judul.strip()
            existing.teks_mentah = teks
            existing.snapshot = snap
            existing.jenis = body.jenis
            existing.kategori_id = body.kategori_id
            sisa.append(existing)
        elif existing is not None:
            db.delete(existing)
    db.commit()
    material2, quizzes2 = _bank_doc_parts(db, user, grup)
    return _bank_document_out(material2, quizzes2, grup)


@router.delete("/documents/{grup}", dependencies=[Depends(require_csrf)])
def delete_bank_document(grup: str, user: User = Depends(staff), db: Session = Depends(get_db)):
    material, quizzes = _bank_doc_parts(db, user, grup)
    _bank_document_out(material, quizzes, grup)
    for s in quizzes:
        db.delete(s)
    if material is not None:
        db.delete(material)
    db.commit()
    return {"ok": True}


@router.post("/documents/{grup}/use", status_code=201, dependencies=[Depends(require_csrf)])
def use_bank_document(grup: str, body: BankDocUseIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Pakai dokumen bank ke pertemuan: pasangan dibuat ulang dengan grup baru."""
    import uuid

    from ..access import get_meeting, get_subject, require_subject_manage
    from .documents import QuizSettingsIn, buat_kuis_part, buat_material_part, document_out

    material, quizzes = _bank_doc_parts(db, user, grup)
    _bank_document_out(material, quizzes, grup)
    meeting = get_meeting(db, body.meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    jenis = (material or quizzes[0]).jenis
    grup_baru = uuid.uuid4().hex
    if material is not None:
        buat_material_part(
            db, meeting, user,
            judul=material.judul, teks=material.teks_mentah,
            grup=grup_baru, jenis=jenis, tenggat=None,
        )
    for s in quizzes:
        buat_kuis_part(
            db, meeting, user,
            judul=s.judul, teks=s.teks_mentah, tipe=s.tipe,
            grup=grup_baru, jenis=jenis, pengaturan=QuizSettingsIn(),
        )
    db.commit()
    return document_out(db, grup_baru)


@router.post("/documents/{grup}/copy", status_code=201, dependencies=[Depends(require_csrf)])
def copy_bank_document(grup: str, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Salin satu dokumen bank utuh (termasuk dari Jelajahi) dengan grup baru."""
    import uuid

    material, quizzes = _bank_doc_parts(db, user, grup, milik_sendiri=False)
    _bank_document_out(material, quizzes, grup)
    grup_baru = uuid.uuid4().hex
    material_baru = None
    if material is not None:
        material_baru = SavedMaterial(
            judul=material.judul, teks_mentah=material.teks_mentah,
            dibuat_oleh=user.id, kategori_id=None,
            grup_dokumen=grup_baru, jenis=material.jenis,
        )
        db.add(material_baru)
    quizzes_baru = []
    for s in quizzes:
        baru = SavedQuiz(
            judul=s.judul, tipe=s.tipe, teks_mentah=s.teks_mentah,
            snapshot=list(s.snapshot) if isinstance(s.snapshot, list) else s.snapshot,
            dibuat_oleh=user.id, kategori_id=None,
            grup_dokumen=grup_baru, jenis=s.jenis,
        )
        db.add(baru)
        quizzes_baru.append(baru)
    db.commit()
    if material_baru is not None:
        db.refresh(material_baru)
    for s in quizzes_baru:
        db.refresh(s)
    return _bank_document_out(material_baru, quizzes_baru, grup_baru)

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
