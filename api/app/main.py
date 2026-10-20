"""Lifunze API — FastAPI application."""

from enum import Enum
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .routers import admin_users, ai_settings, auth, bank, materials, students, subjects
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
