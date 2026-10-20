"""TCML (Tenebris-Class Markup Language) engine — Lifunze.

Paket ini adalah porting modular dari parser v1 (parsers.py di Tenebris-Class):
- core.py      : Tokenizer + AST builder (tidak tahu tag spesifik)
- legacy.py    : parser format lama v1 (fallback kompatibilitas)
- renderers.py : renderer AST -> HTML materi / struktur soal kuis
- registry.py  : metadata pengelompokan tag per modul (fondasi Paket Parser)
- engine.py    : API publik (parse_material, parse_quiz_mcq, parse_quiz_text)
"""

from .engine import parse_material, parse_quiz_mcq, parse_quiz_text

__all__ = ["parse_material", "parse_quiz_mcq", "parse_quiz_text"]
