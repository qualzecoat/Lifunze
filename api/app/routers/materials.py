"""Router materi & lampiran file (Fase 2).

Materi disimpan sebagai teks TCML mentah; HTML hasil render di-cache di
kolom rendered_html. Simpan/edit DITOLAK bila TCML tidak valid (daftar
error parser dikembalikan) — konten rusak tidak pernah masuk DB.
"""

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import (
    get_material,
    get_meeting,
    get_subject,
    require_subject_manage,
    require_subject_view,
)
from ..config import settings
from ..db import get_db
from ..deps import get_current_user, require_csrf
from ..models import Material, MaterialFile, SavedMaterial, User
from ..tcml import parse_material

router = APIRouter(tags=["materials"])

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".pdf", ".mp4", ".sb3"}
MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".sb3": "application/octet-stream",
}


def material_out(m: Material, subject_id: int | None = None) -> dict:
    return {
        "id": m.id,
        "meeting_id": m.meeting_id,
        "subject_id": subject_id,
        "judul": m.judul,
        "teks_mentah": m.teks_mentah,
        "rendered_html": m.rendered_html,
        "dibuat_oleh": m.dibuat_oleh,
        "files": [
            {
                "id": f.id,
                "original_filename": f.original_filename,
                "mime_type": f.mime_type,
                "size_bytes": f.size_bytes,
            }
            for f in m.files
        ],
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _parse_or_400(teks: str) -> str:
    res = parse_material(teks)
    if not res["success"]:
        raise HTTPException(
            status_code=400,
            detail={"pesan": "Teks TCML tidak valid.", "errors": res["errors"]},
        )
    return res["content"]


def _subject_of_material(db: Session, m: Material):
    meeting = get_meeting(db, m.meeting_id)
    return get_subject(db, meeting.subject_id), meeting


class MaterialIn(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    teks_mentah: str = Field(min_length=1)


@router.post("/api/v1/meetings/{meeting_id}/materials", status_code=201, dependencies=[Depends(require_csrf)])
def create_material(
    meeting_id: int,
    body: MaterialIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = get_meeting(db, meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    html = _parse_or_400(body.teks_mentah)
    m = Material(
        meeting_id=meeting.id,
        judul=body.judul.strip(),
        teks_mentah=body.teks_mentah,
        rendered_html=html,
        dibuat_oleh=user.id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return material_out(m, subject.id)


@router.post("/api/v1/meetings/{meeting_id}/materials/from-bank/{saved_id}", status_code=201, dependencies=[Depends(require_csrf)])
def create_material_from_bank(
    meeting_id: int,
    saved_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Salin materi dari bank milik user ke pertemuan ini (parse ulang untuk cache segar)."""
    saved = db.get(SavedMaterial, saved_id)
    if saved is None or saved.dibuat_oleh != user.id:
        raise HTTPException(status_code=404, detail="Materi bank tidak ditemukan.")
    meeting = get_meeting(db, meeting_id)
    subject = get_subject(db, meeting.subject_id)
    require_subject_manage(db, user, subject)
    html = _parse_or_400(saved.teks_mentah)
    m = Material(
        meeting_id=meeting.id,
        judul=saved.judul,
        teks_mentah=saved.teks_mentah,
        rendered_html=html,
        dibuat_oleh=user.id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return material_out(m, subject.id)


@router.get("/api/v1/materials/{material_id}")
def get_one_material(
    material_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_view(db, user, subject)
    return material_out(m, subject.id)


@router.patch("/api/v1/materials/{material_id}", dependencies=[Depends(require_csrf)])
def update_material(
    material_id: int,
    body: MaterialIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_manage(db, user, subject)
    html = _parse_or_400(body.teks_mentah)  # gagal -> materi lama tidak berubah
    m.judul = body.judul.strip()
    m.teks_mentah = body.teks_mentah
    m.rendered_html = html
    db.commit()
    db.refresh(m)
    return material_out(m, subject.id)


@router.delete("/api/v1/materials/{material_id}", dependencies=[Depends(require_csrf)])
def delete_material(
    material_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_manage(db, user, subject)
    for f in list(m.files):
        _remove_file_from_disk(f.storage_key)
    db.delete(m)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------- files
def _storage_path(storage_key: str) -> str:
    return os.path.join(settings.storage_dir, storage_key)


def _remove_file_from_disk(storage_key: str) -> None:
    try:
        os.remove(_storage_path(storage_key))
    except OSError:
        pass


@router.post("/api/v1/materials/{material_id}/files", status_code=201, dependencies=[Depends(require_csrf)])
async def upload_file(
    material_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_manage(db, user, subject)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Format file tidak didukung. Gunakan PNG, JPG, PDF, MP4, atau SB3.")
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Ukuran file melebihi {settings.max_upload_mb} MB.")

    safe_name = os.path.basename(file.filename or f"file{ext}").replace("/", "_")
    storage_key = f"materials/{m.id}/{uuid.uuid4().hex}_{safe_name}"
    path = _storage_path(storage_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as out:
        out.write(content)

    rec = MaterialFile(
        material_id=m.id,
        storage_key=storage_key,
        original_filename=safe_name,
        mime_type=MIME_BY_EXT[ext],
        size_bytes=len(content),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {
        "id": rec.id,
        "original_filename": rec.original_filename,
        "mime_type": rec.mime_type,
        "size_bytes": rec.size_bytes,
    }


@router.get("/api/v1/files/{file_id}")
def download_file(
    file_id: int,
    hemat: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = db.get(MaterialFile, file_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    m = get_material(db, rec.material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_view(db, user, subject)
    path = _storage_path(rec.storage_key)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan di penyimpanan.")
    # Mode hemat kuota (Fase 6): gambar disajikan sebagai varian terkompresi
    # (dibuat malas/lazy saat pertama diminta, lalu di-cache di disk).
    if hemat and (rec.mime_type or "").startswith("image/"):
        hemat_path = path + ".hemat.jpg"
        if not os.path.exists(hemat_path):
            try:
                from PIL import Image

                img = Image.open(path)
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                    bg = Image.new("RGBA", img.size, "WHITE")
                    img = Image.alpha_composite(bg, img).convert("RGB")
                else:
                    img = img.convert("RGB")
                img.thumbnail((1280, 1280))
                img.save(hemat_path, "JPEG", quality=72)
            except Exception:
                hemat_path = path  # gagal kompres -> sajikan asli
        if hemat_path != path:
            stem = os.path.splitext(rec.original_filename)[0]
            return FileResponse(hemat_path, media_type="image/jpeg", filename=f"{stem}_hemat.jpg")
    return FileResponse(path, media_type=rec.mime_type or "application/octet-stream", filename=rec.original_filename)


@router.delete("/api/v1/materials/{material_id}/files/{file_id}", dependencies=[Depends(require_csrf)])
def delete_file(
    material_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_manage(db, user, subject)
    rec = db.get(MaterialFile, file_id)
    if rec is None or rec.material_id != m.id:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    _remove_file_from_disk(rec.storage_key)
    db.delete(rec)
    db.commit()
    return {"ok": True}
