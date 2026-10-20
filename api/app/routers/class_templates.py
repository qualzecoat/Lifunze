"""Router Template Kelas (paket perbaikan 2026-10-20, permintaan Qualze).

Satu kelas utuh (pertemuan + materi + kuis) bisa disimpan sebagai template
lalu dipakai membuat kelas baru dengan isi yang sama:
- Lampiran materi DISALIN fisik ke storage/templates/<id>/ saat menyimpan,
  dan disalin lagi menjadi file materi baru saat template dipakai — template
  tidak bergantung pada file kelas asalnya.
- Jendela buka/tutup kuis dan tanggal pertemuan TIDAK disalin (jadwal kelas
  baru berbeda); durasi & pengaturan acak kuis ikut disalin.
- Siswa tidak pernah ikut — kelas baru selalu mulai kosong.
"""

import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import get_subject, require_subject_manage
from ..config import settings
from ..db import get_db
from ..deps import get_current_user, require_csrf, require_roles
from ..models import (
    ClassTemplate,
    Material,
    MaterialFile,
    Meeting,
    Quiz,
    Subject,
    User,
)
from ..tcml import parse_material
from ..tcml.quiz import parse_quiz_v2

router = APIRouter(tags=["class-templates"])
staff = require_roles("guru", "admin")


def _path(storage_key: str) -> str:
    return os.path.join(settings.storage_dir, storage_key)


def _template_out(t: ClassTemplate) -> dict:
    data = t.data or {}
    meetings = data.get("meetings", [])
    return {
        "id": t.id,
        "nama": t.nama,
        "deskripsi": t.deskripsi,
        "jumlah_pertemuan": len(meetings),
        "jumlah_materi": sum(len(m.get("materials", [])) for m in meetings),
        "jumlah_kuis": sum(len(m.get("quizzes", [])) for m in meetings),
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


class SaveTemplateIn(BaseModel):
    nama: Optional[str] = Field(default=None, max_length=200)
    deskripsi: Optional[str] = None


@router.post("/api/v1/subjects/{subject_id}/save-template", status_code=201, dependencies=[Depends(require_csrf)])
def save_template(
    subject_id: int,
    body: SaveTemplateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = get_subject(db, subject_id)
    require_subject_manage(db, user, subject)

    t = ClassTemplate(
        pemilik_id=user.id,
        nama=(body.nama or subject.nama).strip() or subject.nama,
        deskripsi=body.deskripsi if body.deskripsi is not None else subject.deskripsi,
        data={"meetings": []},
    )
    db.add(t)
    db.flush()  # dapatkan id untuk folder file template

    meetings_data = []
    meetings = (
        db.query(Meeting).filter(Meeting.subject_id == subject.id).order_by(Meeting.urutan).all()
    )
    for m in meetings:
        materials_data = []
        for mt in db.query(Material).filter(Material.meeting_id == m.id).order_by(Material.id):
            files_data = []
            for f in mt.files:
                src = _path(f.storage_key)
                if not os.path.exists(src):
                    continue
                new_key = f"templates/{t.id}/{uuid.uuid4().hex}_{os.path.basename(f.storage_key)}"
                dst = _path(new_key)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
                files_data.append(
                    {
                        "storage_key": new_key,
                        "original_filename": f.original_filename,
                        "mime_type": f.mime_type,
                        "size_bytes": f.size_bytes,
                    }
                )
            materials_data.append(
                {
                    "judul": mt.judul,
                    "teks_mentah": mt.teks_mentah,
                    "grup_dokumen": mt.grup_dokumen,
                    "jenis": mt.jenis,
                    "files": files_data,
                }
            )
        quizzes_data = [
            {
                "judul": q.judul,
                "tipe": q.tipe,
                "teks_mentah": q.teks_mentah,
                "durasi_menit": q.durasi_menit,
                "acak_soal": q.acak_soal,
                "acak_opsi": q.acak_opsi,
                "tampilkan_kunci": q.tampilkan_kunci,
                "grup_dokumen": q.grup_dokumen,
                "jenis": q.jenis,
            }
            for q in db.query(Quiz).filter(Quiz.meeting_id == m.id).order_by(Quiz.id)
        ]
        meetings_data.append(
            {
                "judul": m.judul,
                "deskripsi": m.deskripsi,
                "materials": materials_data,
                "quizzes": quizzes_data,
            }
        )
    t.data = {"meetings": meetings_data}
    db.commit()
    db.refresh(t)
    return _template_out(t)


@router.get("/api/v1/class-templates")
def list_templates(user: User = Depends(staff), db: Session = Depends(get_db)):
    q = db.query(ClassTemplate)
    if user.role == "guru":
        q = q.filter(ClassTemplate.pemilik_id == user.id)
    rows = q.order_by(ClassTemplate.id.desc()).all()
    return [_template_out(t) for t in rows]


def _own_template(db: Session, user: User, template_id: int) -> ClassTemplate:
    t = db.get(ClassTemplate, template_id)
    if t is None or (user.role != "admin" and t.pemilik_id != user.id):
        raise HTTPException(status_code=404, detail="Template kelas tidak ditemukan.")
    return t


@router.delete("/api/v1/class-templates/{template_id}", dependencies=[Depends(require_csrf)])
def delete_template(
    template_id: int,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    t = _own_template(db, user, template_id)
    folder = _path(f"templates/{t.id}")
    db.delete(t)
    db.commit()
    shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True}


class InstantiateIn(BaseModel):
    nama: str = Field(min_length=1, max_length=200)
    deskripsi: Optional[str] = None


@router.post("/api/v1/class-templates/{template_id}/instantiate", status_code=201, dependencies=[Depends(require_csrf)])
def instantiate_template(
    template_id: int,
    body: InstantiateIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    from .quizzes import _create_questions

    t = _own_template(db, user, template_id)
    data = t.data or {}
    subject = Subject(
        nama=body.nama.strip(),
        deskripsi=body.deskripsi if body.deskripsi is not None else t.deskripsi,
        dibuat_oleh=user.id,
    )
    db.add(subject)
    db.flush()

    for i, mdata in enumerate(data.get("meetings", []), start=1):
        meeting = Meeting(
            subject_id=subject.id,
            judul=mdata.get("judul") or f"Pertemuan {i}",
            urutan=i,
            tanggal=None,  # jadwal tidak disalin
            deskripsi=mdata.get("deskripsi"),
        )
        db.add(meeting)
        db.flush()
        # Pasangan dokumen terpadu: grup lama dipetakan ke grup baru agar
        # materi & kuis yang satu dokumen tetap berpasangan di kelas hasil.
        grup_map: dict[str, str] = {}

        def _grup_baru(grup_lama):
            if not grup_lama:
                return None
            if grup_lama not in grup_map:
                grup_map[grup_lama] = uuid.uuid4().hex
            return grup_map[grup_lama]

        for mtdata in mdata.get("materials", []):
            parsed = parse_material(mtdata.get("teks_mentah", ""))
            material = Material(
                meeting_id=meeting.id,
                judul=mtdata.get("judul") or "Materi",
                teks_mentah=mtdata.get("teks_mentah", ""),
                rendered_html=parsed["content"] if parsed["success"] else "",
                dibuat_oleh=user.id,
                grup_dokumen=_grup_baru(mtdata.get("grup_dokumen")),
                jenis=mtdata.get("jenis") or "materi",
                tenggat=None,  # tenggat tidak disalin
            )
            db.add(material)
            db.flush()
            for fdata in mtdata.get("files", []):
                src = _path(fdata["storage_key"])
                if not os.path.exists(src):
                    continue
                safe = os.path.basename(fdata.get("original_filename") or "file")
                new_key = f"materials/{material.id}/{uuid.uuid4().hex}_{safe}"
                dst = _path(new_key)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
                db.add(
                    MaterialFile(
                        material_id=material.id,
                        storage_key=new_key,
                        original_filename=fdata.get("original_filename") or safe,
                        mime_type=fdata.get("mime_type"),
                        size_bytes=fdata.get("size_bytes"),
                    )
                )
        for qdata in mdata.get("quizzes", []):
            quiz = Quiz(
                meeting_id=meeting.id,
                judul=qdata.get("judul") or "Kuis",
                tipe=qdata.get("tipe") or "pilihan_ganda",
                teks_mentah=qdata.get("teks_mentah", ""),
                durasi_menit=qdata.get("durasi_menit"),
                dibuka_pada=None,  # jendela tidak disalin
                ditutup_pada=None,
                acak_soal=bool(qdata.get("acak_soal")),
                acak_opsi=bool(qdata.get("acak_opsi")),
                tampilkan_kunci=bool(qdata.get("tampilkan_kunci", True)),
                dibuat_oleh=user.id,
                grup_dokumen=_grup_baru(qdata.get("grup_dokumen")),
                jenis=qdata.get("jenis") or "kuis",
            )
            db.add(quiz)
            db.flush()
            parsed = parse_quiz_v2(quiz.teks_mentah, expected_type=quiz.tipe)
            if parsed["success"]:
                _create_questions(db, quiz, parsed["content"]["questions"])
    db.commit()
    return {"id": subject.id, "nama": subject.nama}
