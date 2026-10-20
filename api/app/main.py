"""Lifunze API — FastAPI application."""

from enum import Enum
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .routers import (
    admin_users,
    ai_settings,
    auth,
    bank,
    generate,
    learning,
    materials,
    packs,
    quizzes,
    students,
    subjects,
)
from .tcml import parse_material, parse_quiz_mcq, parse_quiz_text
from .tcml.registry import MODULES

app = FastAPI(title="Lifunze API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(students.router)
app.include_router(ai_settings.router)
app.include_router(subjects.router)
app.include_router(materials.router)
app.include_router(bank.router)
app.include_router(quizzes.router)
app.include_router(packs.router)
app.include_router(generate.router)
app.include_router(learning.router)


class ParseKind(str, Enum):
    material = "material"
    quiz_pg = "quiz_pg"
    quiz_esai = "quiz_esai"


class ParseRequest(BaseModel):
    teks: str = Field(..., description="Teks mentah TCML (atau format legacy)")
    jenis: ParseKind = ParseKind.material


class ParseResponse(BaseModel):
    success: bool
    content: Any
    errors: list


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@app.post("/api/v1/parse/content", response_model=ParseResponse)
def parse_content(req: ParseRequest):
    """Validasi & parse teks TCML. Pengganti /api/parse_quiz_raw v1."""
    if req.jenis == ParseKind.material:
        res = parse_material(req.teks)
    elif req.jenis == ParseKind.quiz_pg:
        res = parse_quiz_mcq(req.teks)
    else:
        res = parse_quiz_text(req.teks)
    return ParseResponse(success=res["success"], content=res["content"], errors=res["errors"])


@app.get("/api/v1/tcml/modules")
def list_modules():
    """Metadata modul tag TCML — fondasi menu Paket Parser (Fase 5)."""
    return MODULES


class QuizParseRequest(BaseModel):
    teks: str = Field(..., description="Teks mentah TCML kuis")
    tipe: str = Field(default="pilihan_ganda", pattern="^(pilihan_ganda|teks)$")


@app.post("/api/v1/parse/quiz")
def parse_quiz_endpoint(req: QuizParseRequest):
    """Parse kuis TCML v2 (bobot & multi-jawaban) untuk pratinjau editor."""
    from .tcml.quiz import parse_quiz_v2

    res = parse_quiz_v2(req.teks, expected_type=req.tipe)
    return {"success": res["success"], "content": res["content"], "errors": res["errors"]}
