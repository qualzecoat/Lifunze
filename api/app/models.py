"""Model data Lifunze — SQLAlchemy 2, sesuai blueprint Bagian 5.

Catatan:
- Kolom JSONB (PostgreSQL) dideklarasikan via with_variant agar migrasi
  tetap bisa diuji di SQLite: di PostgreSQL -> JSONB, di SQLite -> JSON.
- Hapus cascading mengikuti semantik v1 (hapus subject -> seluruh isinya ikut).
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

JSONB_TYPE = JSON().with_variant(JSONB(), "postgresql")

now = func.now()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=now, onupdate=now
    )


# ---------------------------------------------------------------- 5.1 Users
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    nama_lengkap: Mapped[Optional[str]] = mapped_column(String(200))
    email: Mapped[Optional[str]] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # admin | guru | siswa
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(50))
    target_id: Mapped[Optional[int]] = mapped_column(Integer)
    # nama kolom di DB "metadata"; attr python "meta" (metadata reserved oleh SQLAlchemy)
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=now)


# ---------------------------------------------------------------- 5.2 Pengaturan AI
class AiSetting(Base, TimestampMixin):
    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(200))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- 5.3 Pembelajaran
class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(200), nullable=False)
    deskripsi: Mapped[Optional[str]] = mapped_column(Text)
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    meetings: Mapped[list["Meeting"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", order_by="Meeting.urutan"
    )


class Enrollment(Base):
    __tablename__ = "enrollments"

    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), primary_key=True)
    enrolled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=now)


class Meeting(Base, TimestampMixin):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    judul: Mapped[str] = mapped_column(String(200), nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, nullable=False)
    tanggal: Mapped[Optional[date]] = mapped_column(Date)
    deskripsi: Mapped[Optional[str]] = mapped_column(Text)

    subject: Mapped["Subject"] = relationship(back_populates="meetings")
    materials: Mapped[list["Material"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class Material(Base, TimestampMixin):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    judul: Mapped[str] = mapped_column(String(200), nullable=False)
    teks_mentah: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[Optional[str]] = mapped_column(Text)  # cache hasil render TCML
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    meeting: Mapped["Meeting"] = relationship(back_populates="materials")
    files: Mapped[list["MaterialFile"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )


class MaterialFile(Base):
    __tablename__ = "material_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)

    material: Mapped["Material"] = relationship(back_populates="files")


# ---------------------------------------------------------------- 5.4 Kuis
class Quiz(Base, TimestampMixin):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    judul: Mapped[str] = mapped_column(String(200), nullable=False)
    tipe: Mapped[str] = mapped_column(String(20), nullable=False)  # pilihan_ganda | teks
    teks_mentah: Mapped[str] = mapped_column(Text, nullable=False)  # TCML kanonis
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    durasi_menit: Mapped[Optional[int]] = mapped_column(Integer)
    acak_soal: Mapped[bool] = mapped_column(Boolean, default=False)
    acak_opsi: Mapped[bool] = mapped_column(Boolean, default=False)
    dibuka_pada: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ditutup_pada: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    tampilkan_kunci: Mapped[bool] = mapped_column(Boolean, default=True)

    meeting: Mapped["Meeting"] = relationship(back_populates="quizzes")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="Question.urutan"
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    tipe: Mapped[str] = mapped_column(String(20), nullable=False)  # pilihan_ganda | teks
    pertanyaan: Mapped[str] = mapped_column(Text, nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, default=0)
    bobot: Mapped[float] = mapped_column(Float, default=1.0)
    jawaban_referensi: Mapped[Optional[str]] = mapped_column(Text)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(2), nullable=False)  # A, B, C, ...
    teks: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    question: Mapped["Question"] = relationship(back_populates="options")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    siswa_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=now)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    skor: Mapped[Optional[float]] = mapped_column(Float)

    quiz: Mapped["Quiz"] = relationship(back_populates="attempts")
    answers: Mapped[list["AttemptAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    option_id: Mapped[Optional[int]] = mapped_column(ForeignKey("question_options.id"))
    jawaban_teks: Mapped[Optional[str]] = mapped_column(Text)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    poin: Mapped[Optional[float]] = mapped_column(Float)

    attempt: Mapped["QuizAttempt"] = relationship(back_populates="answers")


# ---------------------------------------------------------------- 5.5 Bank
class SavedCategory(Base):
    __tablename__ = "saved_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(100), nullable=False)
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class SavedMaterial(Base):
    __tablename__ = "saved_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    judul: Mapped[str] = mapped_column(String(200), nullable=False)
    teks_mentah: Mapped[str] = mapped_column(Text, nullable=False)
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kategori_id: Mapped[Optional[int]] = mapped_column(ForeignKey("saved_categories.id"))


class SavedQuiz(Base):
    __tablename__ = "saved_quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    judul: Mapped[str] = mapped_column(String(200), nullable=False)
    tipe: Mapped[str] = mapped_column(String(20), nullable=False)
    teks_mentah: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[Optional[dict]] = mapped_column(JSONB_TYPE)  # struktur soal (impor tanpa parse ulang)
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kategori_id: Mapped[Optional[int]] = mapped_column(ForeignKey("saved_categories.id"))


# ---------------------------------------------------------------- 5.6 Paket Parser & Generate AI
class TagModule(Base):
    __tablename__ = "tag_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    deskripsi: Mapped[Optional[str]] = mapped_column(Text)
    spec_fragment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)

    examples: Mapped[list["TagExample"]] = relationship(
        back_populates="module", cascade="all, delete-orphan"
    )


class TagExample(Base):
    __tablename__ = "tag_examples"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("tag_modules.id"), nullable=False)
    judul: Mapped[str] = mapped_column(String(200), nullable=False)
    konten: Mapped[str] = mapped_column(Text, nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, default=0)

    module: Mapped["TagModule"] = relationship(back_populates="examples")


class ParserPack(Base, TimestampMixin):
    __tablename__ = "parser_packs"

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(200), nullable=False)
    deskripsi: Mapped[Optional[str]] = mapped_column(Text)
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    visibilitas: Mapped[str] = mapped_column(String(20), default="private")
    allowed_roots: Mapped[list] = mapped_column(JSON, default=list)

    modules: Mapped[list["ParserPackModule"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan", order_by="ParserPackModule.urutan"
    )


class ParserPackModule(Base):
    __tablename__ = "parser_pack_modules"

    pack_id: Mapped[int] = mapped_column(ForeignKey("parser_packs.id"), primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("tag_modules.id"), primary_key=True)
    urutan: Mapped[int] = mapped_column(Integer, default=0)

    pack: Mapped["ParserPack"] = relationship(back_populates="modules")


class ParserPackShare(Base):
    __tablename__ = "parser_pack_shares"
    __table_args__ = (UniqueConstraint("pack_id", "shared_with_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pack_id: Mapped[int] = mapped_column(ForeignKey("parser_packs.id"), nullable=False)
    shared_with_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))  # NULL = semua guru


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    pack_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parser_packs.id"))
    ai_setting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_settings.id"))
    brief: Mapped[Optional[dict]] = mapped_column(JSON)
    prompt_final: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    raw_output: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ContentDraft(Base, TimestampMixin):
    __tablename__ = "content_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    generation_job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("generation_jobs.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    jenis: Mapped[str] = mapped_column(String(20), nullable=False)  # material | quiz
    tipe_quiz: Mapped[Optional[str]] = mapped_column(String(20))
    judul: Mapped[str] = mapped_column(String(200), nullable=False)
    teks_mentah: Mapped[str] = mapped_column(Text, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    errors: Mapped[Optional[list]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    published_id: Mapped[Optional[int]] = mapped_column(Integer)


# ---------------------------------------------------------------- 5.7 Fitur lanjutan (skema disiapkan)
class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    judul: Mapped[str] = mapped_column(String(200), nullable=False)
    isi: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    tipe: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=now)


class Submission(Base, TimestampMixin):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    siswa_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    catatan: Mapped[Optional[str]] = mapped_column(Text)
    skor: Mapped[Optional[float]] = mapped_column(Float)
    feedback_rubrik: Mapped[Optional[dict]] = mapped_column(JSON)
    dinilai_oleh: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))


class MaterialRead(Base):
    __tablename__ = "material_reads"
    __table_args__ = (UniqueConstraint("material_id", "siswa_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    siswa_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=now)
