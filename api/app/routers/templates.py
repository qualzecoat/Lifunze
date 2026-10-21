"""Router Template Alur Mengajar / Pedagogi (2026-10-21).

Template merujuk paket parser (atau paket dasar) dan menentukan urutan
bagian materi. Mutasi owner-only (keputusan D1); template bawaan sistem
(dibuat_oleh NULL) tidak bisa diubah/dihapus — fork dulu. Berbagi v1:
visibilitas "shared" = terlihat semua guru.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_csrf, require_roles
from ..models import ParserPack, PedagogyTemplate, Subject, User
from ..paket import can_access_pack
from ..pedagogi import (
    can_access_template,
    ensure_preset_templates,
    resolve_pack,
    spec_for_template,
    template_out,
    validate_bagian,
)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])
staff = require_roles("guru", "admin")


def _get_accessible(db: Session, user: User, tid: int) -> PedagogyTemplate:
    t = db.get(PedagogyTemplate, tid)
    if t is None or not can_access_template(user, t):
        raise HTTPException(status_code=404, detail="Template tidak ditemukan.")
    return t


def _get_owned(db: Session, user: User, tid: int) -> PedagogyTemplate:
    t = db.get(PedagogyTemplate, tid)
    if t is None:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan.")
    if t.dibuat_oleh is None:
        raise HTTPException(
            status_code=403,
            detail="Template bawaan tidak bisa diubah — fork dulu menjadi template Anda.",
        )
    if t.dibuat_oleh != user.id:
        raise HTTPException(status_code=403, detail="Hanya pemilik template yang boleh mengubahnya.")
    return t


def _cek_pack(db: Session, user: User, pack_id: Optional[int]) -> None:
    if pack_id is None:
        return
    pack = db.get(ParserPack, pack_id)
    if pack is None or not can_access_pack(db, user, pack):
        raise HTTPException(status_code=400, detail="Paket parser rujukan tidak ditemukan / tidak bisa diakses.")


class TemplateIn(BaseModel):
    nama: str = Field(min_length=1, max_length=200)
    deskripsi: Optional[str] = None
    pack_id: Optional[int] = None
    paket_dasar: bool = True
    bagian: list = Field(default_factory=list)


@router.get("")
def list_templates(user: User = Depends(staff), db: Session = Depends(get_db)):
    ensure_preset_templates(db)
    rows = db.query(PedagogyTemplate).order_by(PedagogyTemplate.nama).all()
    preset, saya, dibagikan = [], [], []
    for t in rows:
        if t.dibuat_oleh is None:
            preset.append(template_out(db, t, user))
        elif t.dibuat_oleh == user.id:
            saya.append(template_out(db, t, user))
        elif can_access_template(user, t):
            dibagikan.append(template_out(db, t, user))
    return {"preset": preset, "saya": saya, "dibagikan": dibagikan}


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_template(body: TemplateIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    _cek_pack(db, user, body.pack_id)
    try:
        bagian = validate_bagian(body.bagian)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    t = PedagogyTemplate(
        nama=body.nama.strip(),
        deskripsi=body.deskripsi,
        dibuat_oleh=user.id,
        visibilitas="private",
        pack_id=body.pack_id,
        paket_dasar=body.paket_dasar,
        bagian=bagian,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return template_out(db, t, user)


@router.get("/{template_id}")
def get_template(template_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    t = _get_accessible(db, user, template_id)
    return template_out(db, t, user)


@router.patch("/{template_id}", dependencies=[Depends(require_csrf)])
def update_template(
    template_id: int,
    body: TemplateIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    t = _get_owned(db, user, template_id)
    _cek_pack(db, user, body.pack_id)
    try:
        bagian = validate_bagian(body.bagian)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    t.nama = body.nama.strip()
    t.deskripsi = body.deskripsi
    t.pack_id = body.pack_id
    t.paket_dasar = body.paket_dasar
    t.bagian = bagian
    db.commit()
    db.refresh(t)
    return template_out(db, t, user)


@router.delete("/{template_id}", dependencies=[Depends(require_csrf)])
def delete_template(template_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    t = _get_owned(db, user, template_id)
    # Lepas rujukan default kelas agar FK tidak menahan penghapusan.
    db.query(Subject).filter(Subject.template_default_id == t.id).update(
        {Subject.template_default_id: None}, synchronize_session=False
    )
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/{template_id}/fork", status_code=201, dependencies=[Depends(require_csrf)])
def fork_template(template_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    src = _get_accessible(db, user, template_id)
    t = PedagogyTemplate(
        nama=src.nama if src.dibuat_oleh == user.id else f"{src.nama} (Fork)",
        deskripsi=src.deskripsi,
        dibuat_oleh=user.id,
        visibilitas="private",
        pack_id=src.pack_id,
        paket_dasar=src.paket_dasar,
        bagian=[dict(b) for b in (src.bagian or [])],
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return template_out(db, t, user)


class ShareIn(BaseModel):
    mode: str = Field(pattern="^(private|shared)$")


@router.put("/{template_id}/share", dependencies=[Depends(require_csrf)])
def share_template(
    template_id: int,
    body: ShareIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    t = _get_owned(db, user, template_id)
    t.visibilitas = body.mode
    db.commit()
    db.refresh(t)
    return template_out(db, t, user)


class PreviewSpecIn(BaseModel):
    bagian: list = Field(default_factory=list)
    pack_id: Optional[int] = None
    paket_dasar: bool = True
    template_id: Optional[int] = None


@router.post("/preview-spec", dependencies=[Depends(require_csrf)])
def preview_spec(body: PreviewSpecIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Spec tersaring untuk kombinasi template+paket (pratinjau prompt di
    Mode Lanjutan): menunjukkan hematnya penyaringan oleh template."""
    if body.template_id:
        t = _get_accessible(db, user, body.template_id)
    else:
        try:
            bagian = validate_bagian(body.bagian)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        t = PedagogyTemplate(
            nama="(pratinjau)", dibuat_oleh=user.id,
            pack_id=body.pack_id, paket_dasar=body.paket_dasar, bagian=bagian,
        )
    pack = resolve_pack(db, user, t)
    if pack is None:
        raise HTTPException(status_code=400, detail="Tidak ada paket yang bisa dipakai.")
    spec = spec_for_template(db, t, pack)
    return {"spec": spec, "karakter": len(spec), "pack_id": pack.id, "pack_nama": pack.nama}
