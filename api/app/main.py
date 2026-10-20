"""Lifunze API — FastAPI application."""

from enum import Enum
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import settings
from .tcml import parse_material, parse_quiz_mcq, parse_quiz_text
from .tcml.registry import MODULES

app = FastAPI(title="Lifunze API", version="0.1.0")


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
