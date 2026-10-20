"""Router Paket Parser (Fase 5).

Paket = komposisi modul tag TCML. Pemilik bisa membagikan paket ke guru
tertentu atau semua guru (baris share shared_with_id NULL); penerima boleh
memakai & mem-fork, hanya pemilik yang boleh mengubah/menghapus.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_csrf, require_roles
from ..models import ParserPack, ParserPackModule, ParserPackShare, TagModule, User
from ..paket import (
    build_export_markdown,
    build_system_prompt,
    can_access_pack,
    effective_tag_pilihan,
    ensure_preset_packs,
    normalize_tag_pilihan,
    pack_module_rows,
    pack_shares,
    roots_for_slugs,
    spec_text_for_selection,
    sync_tag_modules,
    validate_document,
)
from ..tcml.registry import MODULES as REGISTRY_MODULES

router = APIRouter(prefix="/api/v1/packs", tags=["packs"])
staff = require_roles("guru", "admin")


def _pack_out(db: Session, pack: ParserPack, viewer: User) -> dict:
    owner = db.get(User, pack.dibuat_oleh)
    shares = pack_shares(db, pack)
    return {
        "id": pack.id,
        "nama": pack.nama,
        "deskripsi": pack.deskripsi,
        "visibilitas": pack.visibilitas,
        "dibuat_oleh": pack.dibuat_oleh,
        "pemilik": (
            {"id": owner.id, "username": owner.username, "nama_lengkap": owner.nama_lengkap}
            if owner
            else None
        ),
        "punya_saya": pack.dibuat_oleh == viewer.id,
        "modules": [
            {"slug": m.slug, "nama": m.nama} for m in pack_module_rows(db, pack)
        ],
        "tag_pilihan": pack.tag_pilihan,
        "allowed_roots": pack.allowed_roots or [],
        "dibagikan_ke_semua": any(s.shared_with_id is None for s in shares),
        "shared_with_ids": [s.shared_with_id for s in shares if s.shared_with_id is not None],
    }


def _get_pack(db: Session, pack_id: int) -> ParserPack:
    pack = db.get(ParserPack, pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan.")
    return pack


def _get_accessible_pack(db: Session, user: User, pack_id: int) -> ParserPack:
    pack = _get_pack(db, pack_id)
    if not can_access_pack(db, user, pack):
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan.")
    return pack


def _get_owned_pack(db: Session, user: User, pack_id: int) -> ParserPack:
    pack = _get_pack(db, pack_id)
    if pack.dibuat_oleh != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Hanya pemilik paket yang boleh mengubahnya.")
    return pack


def _set_modules(
    db: Session,
    pack: ParserPack,
    module_slugs: list[str],
    tag_pilihan: Optional[dict] = None,
) -> None:
    modules_by_slug = sync_tag_modules(db)
    try:
        normalized = normalize_tag_pilihan(tag_pilihan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if normalized:
        slugs = list(normalized.keys())
    else:
        slugs = list(dict.fromkeys(module_slugs))  # unik, urutan dipertahankan
    unknown = [s for s in slugs if s not in modules_by_slug]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Modul tidak dikenal: {', '.join(unknown)}")
    if not slugs:
        raise HTTPException(status_code=400, detail="Pilih minimal satu modul/tag.")
    db.query(ParserPackModule).filter(ParserPackModule.pack_id == pack.id).delete(
        synchronize_session=False
    )
    db.flush()
    for i, slug in enumerate(slugs):
        db.add(
            ParserPackModule(
                pack_id=pack.id, module_id=modules_by_slug[slug].id, urutan=i
            )
        )
    pack.allowed_roots = roots_for_slugs(slugs)
    pack.tag_pilihan = normalized


# ------------------------------------------------------------------ katalog
@router.get("/modules")
def list_modules(user: User = Depends(staff), db: Session = Depends(get_db)):
    modules = sync_tag_modules(db)
    out = []
    for slug in modules:
        m = modules[slug]
        reg = REGISTRY_MODULES[slug]

        def _jenis_contoh(konten: str) -> str:
            if "[QUIZ]" in konten:
                return "kuis-pg" if "pilihan_ganda" in konten else "kuis-esai"
            return "material"

        out.append(
            {
                "id": m.id,
                "slug": m.slug,
                "nama": m.nama,
                "deskripsi": m.deskripsi,
                "spec_fragment": m.spec_fragment,
                "ikon": reg.get("ikon", "📦"),
                "roots": reg["roots"],
                "tags": reg["tags"],
                "tags_meta": [
                    {
                        "tag": t,
                        "nama": reg.get("tags_meta", {}).get(t, {}).get("nama", t),
                        "desc": reg.get("tags_meta", {}).get(t, {}).get("desc", ""),
                        "wajib": bool(reg.get("tags_meta", {}).get(t, {}).get("wajib", False)),
                        "spec": reg.get("tags_meta", {}).get(t, {}).get("spec", ""),
                        "contoh": reg.get("tags_meta", {}).get(t, {}).get("contoh", ""),
                        "jenis": reg.get("tags_meta", {}).get(t, {}).get("jenis", "material"),
                    }
                    for t in reg["tags"]
                ],
                "examples": [
                    {"judul": e.judul, "konten": e.konten, "jenis": _jenis_contoh(e.konten)}
                    for e in sorted(m.examples, key=lambda x: x.urutan)
                ],
            }
        )
    return out


# -------------------------------------------------- pratinjau spec & meja uji
class SelectionIn(BaseModel):
    module_slugs: list[str] = []
    tag_pilihan: Optional[dict] = None


def _selection_slugs(body: SelectionIn) -> tuple[list[str], Optional[dict]]:
    """Slug efektif + pilihan tag ternormalisasi dari payload pilihan."""
    try:
        normalized = normalize_tag_pilihan(body.tag_pilihan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if normalized:
        return list(normalized.keys()), normalized
    slugs = [s for s in dict.fromkeys(body.module_slugs) if s in REGISTRY_MODULES]
    return slugs, None


@router.post("/preview-spec", dependencies=[Depends(require_csrf)])
def preview_spec(body: SelectionIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    slugs, normalized = _selection_slugs(body)
    if not slugs:
        return {"spec": "", "karakter": 0}
    spec = spec_text_for_selection(db, slugs, normalized)
    return {"spec": spec, "karakter": len(spec)}


class TestIn(SelectionIn):
    kind: str = Field(pattern="^(materi|kuis_pg|kuis_esai)$")
    teks: str = Field(min_length=1)


@router.post("/test", dependencies=[Depends(require_csrf)])
def test_selection(body: TestIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    slugs, normalized = _selection_slugs(body)
    if not slugs:
        raise HTTPException(status_code=400, detail="Pilih minimal satu modul/tag dulu.")
    eff = effective_tag_pilihan(slugs, normalized)
    transient = ParserPack(
        nama="(meja uji)",
        dibuat_oleh=user.id,
        visibilitas="private",
        allowed_roots=roots_for_slugs(slugs),
        tag_pilihan=eff,
    )
    return validate_document(db, transient, body.kind, body.teks)


@router.get("/recipients")
def list_recipients(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = (
        db.query(User)
        .filter(User.role.in_(["guru", "admin"]), User.deleted_at.is_(None))
        .order_by(User.username)
        .all()
    )
    return [
        {"id": u.id, "username": u.username, "nama_lengkap": u.nama_lengkap, "role": u.role}
        for u in rows
        if u.id != user.id
    ]


# --------------------------------------------------------------------- CRUD
class PackIn(BaseModel):
    nama: str = Field(min_length=1, max_length=200)
    deskripsi: Optional[str] = None
    module_slugs: list[str] = Field(min_length=1)
    tag_pilihan: Optional[dict] = None


@router.get("")
def list_my_packs(user: User = Depends(staff), db: Session = Depends(get_db)):
    ensure_preset_packs(db, user)
    rows = (
        db.query(ParserPack)
        .filter(ParserPack.dibuat_oleh == user.id)
        .order_by(ParserPack.nama)
        .all()
    )
    return [_pack_out(db, p, user) for p in rows]


@router.get("/shared")
def list_shared_packs(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.query(ParserPack).filter(ParserPack.dibuat_oleh != user.id).all()
    return [_pack_out(db, p, user) for p in rows if can_access_pack(db, user, p)]


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_pack(body: PackIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    pack = ParserPack(
        nama=body.nama.strip(),
        deskripsi=body.deskripsi,
        dibuat_oleh=user.id,
        visibilitas="private",
        allowed_roots=[],
    )
    db.add(pack)
    db.flush()
    _set_modules(db, pack, body.module_slugs, body.tag_pilihan)
    db.commit()
    db.refresh(pack)
    return _pack_out(db, pack, user)


@router.get("/{pack_id}")
def get_pack(pack_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    pack = _get_accessible_pack(db, user, pack_id)
    out = _pack_out(db, pack, user)
    out["prompt_preview"] = build_system_prompt(db, pack, "materi")
    return out


@router.patch("/{pack_id}", dependencies=[Depends(require_csrf)])
def update_pack(
    pack_id: int,
    body: PackIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    pack = _get_owned_pack(db, user, pack_id)
    pack.nama = body.nama.strip()
    pack.deskripsi = body.deskripsi
    _set_modules(db, pack, body.module_slugs, body.tag_pilihan)
    db.commit()
    db.refresh(pack)
    return _pack_out(db, pack, user)


@router.delete("/{pack_id}", dependencies=[Depends(require_csrf)])
def delete_pack(pack_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    pack = _get_owned_pack(db, user, pack_id)
    db.delete(pack)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------- bagi & fork
class ShareIn(BaseModel):
    mode: str = Field(pattern="^(private|all|users)$")
    user_ids: list[int] = []


@router.put("/{pack_id}/share", dependencies=[Depends(require_csrf)])
def share_pack(
    pack_id: int,
    body: ShareIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    pack = _get_owned_pack(db, user, pack_id)
    db.query(ParserPackShare).filter(ParserPackShare.pack_id == pack.id).delete(
        synchronize_session=False
    )
    db.flush()
    if body.mode == "all":
        db.add(ParserPackShare(pack_id=pack.id, shared_with_id=None))
        pack.visibilitas = "shared"
    elif body.mode == "users":
        ids = [i for i in dict.fromkeys(body.user_ids) if i != user.id]
        valid = {
            u.id
            for u in db.query(User)
            .filter(User.id.in_(ids), User.role.in_(["guru", "admin"]))
            .all()
        } if ids else set()
        for uid in ids:
            if uid in valid:
                db.add(ParserPackShare(pack_id=pack.id, shared_with_id=uid))
        pack.visibilitas = "shared" if valid else "private"
    else:
        pack.visibilitas = "private"
    db.commit()
    db.refresh(pack)
    return _pack_out(db, pack, user)


@router.post("/{pack_id}/fork", status_code=201, dependencies=[Depends(require_csrf)])
def fork_pack(pack_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    src = _get_accessible_pack(db, user, pack_id)
    modules = pack_module_rows(db, src)
    pack = ParserPack(
        nama=src.nama if src.dibuat_oleh == user.id else f"{src.nama} (Fork)",
        deskripsi=src.deskripsi,
        dibuat_oleh=user.id,
        visibilitas="private",
        allowed_roots=list(src.allowed_roots or []),
        tag_pilihan=dict(src.tag_pilihan) if src.tag_pilihan else None,
    )
    db.add(pack)
    db.flush()
    for i, m in enumerate(modules):
        db.add(ParserPackModule(pack_id=pack.id, module_id=m.id, urutan=i))
    db.commit()
    db.refresh(pack)
    return _pack_out(db, pack, user)


@router.get("/{pack_id}/export")
def export_pack(pack_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    pack = _get_accessible_pack(db, user, pack_id)
    owner = db.get(User, pack.dibuat_oleh)
    md = build_export_markdown(db, pack, owner.nama_lengkap or owner.username if owner else "-")
    filename = f"paket-{pack.nama.lower().replace(' ', '-')}.md"
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
