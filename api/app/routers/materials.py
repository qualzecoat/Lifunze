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
    is_enrolled,
    require_subject_manage,
    require_subject_view,
)
from ..config import settings
from ..db import get_db
from ..deps import get_current_user, require_csrf
from ..models import CekAnswer, Enrollment, Material, MaterialFile, Meeting, SavedMaterial, User
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

# Validasi magic bytes (Fase 8): ekstensi saja tidak dipercaya — isi file
# harus cocok dengan tanda tangan formatnya.
_MAGIC_PREFIXES = {
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".pdf": [b"%PDF"],
    ".sb3": [b"PK\x03\x04"],
    ".zip": [b"PK\x03\x04"],
}


def validate_magic(ext: str, content: bytes) -> bool:
    if ext == ".mp4":
        return len(content) >= 8 and content[4:8] == b"ftyp"
    if ext == ".txt":
        try:
            content[:4096].decode("utf-8")
            return b"\x00" not in content[:4096]
        except UnicodeDecodeError:
            return False
    prefixes = _MAGIC_PREFIXES.get(ext)
    if prefixes is None:
        return False
    return any(content.startswith(p) for p in prefixes)


def material_out(m: Material, subject_id: int | None = None) -> dict:
    return {
        "id": m.id,
        "meeting_id": m.meeting_id,
        "subject_id": subject_id,
        "judul": m.judul,
        "teks_mentah": m.teks_mentah,
        "rendered_html": m.rendered_html,
        "dibuat_oleh": m.dibuat_oleh,
        "grup_dokumen": m.grup_dokumen,
        "jenis": m.jenis,
        "tenggat": m.tenggat.isoformat() if m.tenggat else None,
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


def _material_navigation(db: Session, subject_id: int, current_id: int) -> dict:
    """Materi sebelum/sesudah dalam urutan kelas (pertemuan lalu urutan materi),
    supaya siswa bisa lanjut membaca tanpa kembali ke halaman kelas."""
    rows = (
        db.query(Material.id, Material.judul)
        .join(Meeting, Material.meeting_id == Meeting.id)
        .filter(Meeting.subject_id == subject_id)
        .order_by(Meeting.urutan, Material.id)
        .all()
    )
    ids = [r.id for r in rows]
    if current_id not in ids:
        return {"sebelumnya": None, "berikutnya": None}
    i = ids.index(current_id)

    def brief(r) -> dict | None:
        return {"id": r.id, "judul": r.judul} if r is not None else None

    return {
        "sebelumnya": brief(rows[i - 1]) if i > 0 else None,
        "berikutnya": brief(rows[i + 1]) if i < len(rows) - 1 else None,
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
    out = material_out(m, subject.id)
    if user.role == "siswa":
        # Audit #2: teks_mentah memuat [ANSWER] Cek Pemahaman — siswa hanya
        # boleh menerima HTML render + payload cek yang sudah disaring.
        out["teks_mentah"] = None
    out["navigasi"] = _material_navigation(db, subject.id, m.id)
    if m.grup_dokumen:
        from ..models import Quiz

        pasangan = (
            db.query(Quiz)
            .filter(Quiz.grup_dokumen == m.grup_dokumen)
            .order_by(Quiz.id)
            .all()
        )
        out["dokumen_kuis"] = [
            {
                "id": q.id,
                "judul": q.judul,
                "tipe": q.tipe,
                "dibuka_pada": q.dibuka_pada.isoformat() if q.dibuka_pada else None,
                "ditutup_pada": q.ditutup_pada.isoformat() if q.ditutup_pada else None,
                "durasi_menit": q.durasi_menit,
            }
            for q in pasangan
        ]
    else:
        out["dokumen_kuis"] = []
    out["cek"] = _cek_payload(db, m, user)
    return out


# ------------------------------------------------- Cek Pemahaman [CEK]
def _daftar_cek(m: Material) -> list[dict]:
    """Soal sisipan [CEK] materi ini (bentuk server, memuat kunci)."""
    from ..tcml.cek import extract_ceks

    ceks, errors = extract_ceks(m.teks_mentah or "")
    return [] if errors else ceks


def _skor_cek(ceks: list[dict], jawaban: dict[int, CekAnswer]) -> dict | None:
    """Nilai materi dari Cek Pemahaman — hanya PG yang diskor.

    Audit #4: jawaban hanya dihitung bila indeksnya masih ada di daftar CEK
    saat ini DAN tipe soal pada indeks itu tetap PG — jawaban basi dari
    susunan soal lama tidak boleh menggelembungkan skor (dulu bisa >100%).
    """
    maks = sum(c["bobot"] for c in ceks if c["tipe"] == "pilihan_ganda")
    if maks <= 0:
        return None
    diperoleh = sum(
        (a.skor or 0)
        for i, a in jawaban.items()
        if 0 <= i < len(ceks)
        and ceks[i]["tipe"] == "pilihan_ganda"
        and a.tipe == "pilihan_ganda"
    )
    return {"diperoleh": diperoleh, "maksimal": maks, "persen": round(diperoleh / maks * 100, 1)}


def _tanda_cek(teks: str) -> list[tuple[str, str]] | None:
    """Tanda tangan isi soal sisipan: [(tipe, pertanyaan), ...] per indeks."""
    from ..tcml.cek import extract_ceks

    ceks, errors = extract_ceks(teks or "")
    if errors:
        return None
    return [(c["tipe"], c["pertanyaan"]) for c in ceks]


def pagar_cek(db: Session, m: Material, teks_baru: str) -> None:
    """Audit #4: bila materi ini sudah punya jawaban Cek Pemahaman, daftar
    soal sisipannya (isi & urutan) tidak boleh berubah — jawaban siswa
    terikat nomor urut. Mengedit bagian materi di luar blok [CEK] tetap
    bebas. Dipakai juga oleh editor dokumen."""
    ada = db.query(CekAnswer).filter(CekAnswer.material_id == m.id).first()
    if ada is None:
        return
    lama = _tanda_cek(m.teks_mentah or "")
    baru = _tanda_cek(teks_baru)
    if lama is not None and baru is not None and lama != baru:
        raise HTTPException(
            status_code=400,
            detail=(
                "Soal Cek Pemahaman di materi ini sudah dijawab siswa — isi dan urutan "
                "soal sisipan tidak bisa diubah agar nilai siswa tidak bergeser. "
                "Bagian materi di luar blok [CEK] tetap bisa diedit."
            ),
        )


def _cek_payload(db: Session, m: Material, user: User) -> dict:
    from ..tcml.cek import cek_untuk_siswa

    ceks = _daftar_cek(m)
    is_staff = user.role in ("guru", "admin")
    daftar = []
    for i, c in enumerate(ceks):
        item = cek_untuk_siswa(c, i)
        if is_staff:
            if c["tipe"] == "pilihan_ganda":
                item["kunci"] = [o["label"] for o in c["options"] if o["is_correct"]]
            else:
                item["jawaban_referensi"] = c["jawaban_referensi"]
        daftar.append(item)
    skor = None
    if user.role == "siswa" and ceks:
        rows = (
            db.query(CekAnswer)
            .filter(CekAnswer.material_id == m.id, CekAnswer.siswa_id == user.id)
            .all()
        )
        jawaban = {a.cek_index: a for a in rows}
        for item in daftar:
            a = jawaban.get(item["indeks"])
            item["jawabanku"] = (
                {"jawaban": a.jawaban, "benar": a.benar} if a is not None else None
            )
            # Referensi esai hanya dibuka SETELAH siswa menjawab (keputusan user).
            if a is not None and item["tipe"] == "teks":
                item["jawaban_referensi"] = ceks[item["indeks"]]["jawaban_referensi"]
        skor = _skor_cek(ceks, jawaban)
    return {"daftar": daftar, "skor": skor}


class CekJawabIn(BaseModel):
    jawaban: str = Field(min_length=1, max_length=4000)


@router.post(
    "/api/v1/materials/{material_id}/cek/{cek_index}/jawab",
    dependencies=[Depends(require_csrf)],
)
def jawab_cek(
    material_id: int,
    cek_index: int,
    body: CekJawabIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siswa menjawab satu soal Cek Pemahaman. Boleh diulang — jawaban
    terakhir yang tersimpan & dinilai. PG dinilai seketika; esai membuka
    jawaban referensi untuk cek mandiri setelah menjawab."""
    if user.role != "siswa":
        raise HTTPException(status_code=403, detail="Hanya siswa yang menjawab Cek Pemahaman.")
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    if not is_enrolled(db, user.id, subject.id):
        raise HTTPException(status_code=403, detail="Kamu tidak terdaftar di kelas ini.")
    ceks = _daftar_cek(m)
    if cek_index < 0 or cek_index >= len(ceks):
        raise HTTPException(status_code=404, detail="Soal Cek Pemahaman tidak ditemukan.")
    cek = ceks[cek_index]
    jawaban_teks = body.jawaban.strip()
    if not jawaban_teks:
        raise HTTPException(status_code=400, detail="Jawaban tidak boleh kosong.")

    benar: bool | None = None
    skor: float | None = None
    if cek["tipe"] == "pilihan_ganda":
        dipilih = {t.strip().upper() for t in jawaban_teks.replace(";", ",").split(",") if t.strip()}
        kunci = {o["label"] for o in cek["options"] if o["is_correct"]}
        label_valid = {o["label"] for o in cek["options"]}
        if not dipilih or not dipilih.issubset(label_valid):
            raise HTTPException(status_code=400, detail="Pilihan jawaban tidak valid.")
        benar = dipilih == kunci
        skor = cek["bobot"] if benar else 0.0
        jawaban_simpan = ", ".join(sorted(dipilih))
    else:
        jawaban_simpan = jawaban_teks

    row = (
        db.query(CekAnswer)
        .filter(
            CekAnswer.material_id == m.id,
            CekAnswer.siswa_id == user.id,
            CekAnswer.cek_index == cek_index,
        )
        .first()
    )
    if row is None:
        row = CekAnswer(material_id=m.id, siswa_id=user.id, cek_index=cek_index, tipe=cek["tipe"])
        db.add(row)
    row.tipe = cek["tipe"]  # audit #4: samakan dengan tipe soal saat ini
    row.jawaban = jawaban_simpan
    row.benar = benar
    row.skor = skor
    db.commit()

    rows = (
        db.query(CekAnswer)
        .filter(CekAnswer.material_id == m.id, CekAnswer.siswa_id == user.id)
        .all()
    )
    hasil: dict = {"benar": benar, "skor": _skor_cek(ceks, {a.cek_index: a for a in rows})}
    if cek["tipe"] == "pilihan_ganda":
        hasil["kunci"] = [o["label"] for o in cek["options"] if o["is_correct"]]
        hasil["penjelasan_kunci"] = [
            {"label": o["label"], "teks": o["teks"]} for o in cek["options"] if o["is_correct"]
        ]
    else:
        # Referensi esai HANYA dibuka setelah siswa menjawab (keputusan user).
        hasil["jawaban_referensi"] = cek["jawaban_referensi"]
    return hasil


@router.get("/api/v1/materials/{material_id}/cek/hasil")
def hasil_cek(
    material_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ringkasan Cek Pemahaman per siswa untuk guru/admin kelas ini."""
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_manage(db, user, subject)
    ceks = _daftar_cek(m)
    enrollments = (
        db.query(Enrollment).filter(Enrollment.subject_id == subject.id).all()
    )
    rows = db.query(CekAnswer).filter(CekAnswer.material_id == m.id).all()
    per_siswa: dict[int, dict[int, CekAnswer]] = {}
    for a in rows:
        per_siswa.setdefault(a.siswa_id, {})[a.cek_index] = a
    hasil = []
    for e in enrollments:
        siswa = db.get(User, e.student_id)
        jawaban = per_siswa.get(e.student_id, {})
        skor = _skor_cek(ceks, jawaban)
        hasil.append(
            {
                "siswa_id": e.student_id,
                "nama": (siswa.nama_lengkap or siswa.username) if siswa else "?",
                "terjawab": sum(1 for i in jawaban if 0 <= i < len(ceks)),
                "total": len(ceks),
                "skor_persen": skor["persen"] if skor else None,
            }
        )
    hasil.sort(key=lambda r: r["nama"].lower())
    return {"total_cek": len(ceks), "siswa": hasil}


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
    pagar_cek(db, m, body.teks_mentah)  # audit #4: kunci daftar [CEK] bila sudah dijawab
    html = _parse_or_400(body.teks_mentah)  # gagal -> materi lama tidak berubah
    m.judul = body.judul.strip()
    m.teks_mentah = body.teks_mentah
    m.rendered_html = html
    db.commit()
    db.refresh(m)
    return material_out(m, subject.id)


@router.post("/api/v1/materials/{material_id}/save-to-bank", status_code=201, dependencies=[Depends(require_csrf)])
def save_material_to_bank(
    material_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simpan materi pertemuan ini ke bank pemiliknya — dengan penanda asal.
    Sekali tersimpan, materi yang sama tidak bisa disimpan lagi walau diedit
    (keputusan Qualze, paket perbaikan 2026-10-20)."""
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_manage(db, user, subject)
    sudah = (
        db.query(SavedMaterial)
        .filter(SavedMaterial.dibuat_oleh == user.id, SavedMaterial.asal_id == m.id)
        .first()
    )
    if sudah is not None:
        raise HTTPException(status_code=400, detail="Materi ini sudah ada di bank Anda.")
    saved = SavedMaterial(
        judul=m.judul,
        teks_mentah=m.teks_mentah,
        dibuat_oleh=user.id,
        kategori_id=None,
        asal_id=m.id,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {"id": saved.id, "judul": saved.judul, "asal_id": saved.asal_id}


@router.delete("/api/v1/materials/{material_id}", dependencies=[Depends(require_csrf)])
def delete_material(
    material_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = get_material(db, material_id)
    subject, _ = _subject_of_material(db, m)
    require_subject_manage(db, user, subject)
    kunci_file = [f.storage_key for f in list(m.files)]
    db.delete(m)  # cascade ORM menghapus submission/tanda baca/jawaban CEK (audit #5)
    db.commit()
    # File fisik dihapus SETELAH commit berhasil — dulu file hilang duluan
    # walaupun penghapusan DB-nya gagal (audit #5).
    for kunci in kunci_file:
        _remove_file_from_disk(kunci)
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
    if not validate_magic(ext, content):
        raise HTTPException(
            status_code=400,
            detail="Isi file tidak cocok dengan formatnya (validasi magic bytes gagal). Unggah file aslinya, bukan hasil ganti nama.",
        )

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
