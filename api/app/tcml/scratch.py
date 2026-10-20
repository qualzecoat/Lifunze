"""Renderer tag khusus Scratch (Fase 7) — blueprint: blok, sprite, stage.

- [SCRATCH] : stage — sematan pemutar proyek Scratch/TurboWarp yang bisa
  dimainkan langsung di materi. Demi keamanan, isi tag TIDAK pernah
  disalin mentah ke atribut src: target diurai (ID angka / URL resmi) lalu
  URL embed dibangun ulang dari komponen tervalidasi.
- [BLOCKS]  : blok — notasi teks blok Scratch (scratchblocks) yang
  dirender menjadi blok visual oleh pustaka scratchblocks di frontend;
  tanpa JS, notasi tetap terbaca sebagai teks.
- [SPRITE]  : sprite — kartu info sprite: baris pertama = nama sprite,
  baris berikutnya = penjelasan peran/cara membuatnya.
"""

import re

from markupsafe import escape

_ID_RE = re.compile(r"^\d+$")
_SCRATCH_URL_RE = re.compile(r"^https://scratch\.mit\.edu/projects/(\d+)/?(?:embed)?/?$")
_TURBOWARP_URL_RE = re.compile(r"^https://turbowarp\.org/(?:projects/)?(\d+)/?(?:embed)?/?$")

PROVIDERS = {
    "scratch": {
        "embed": "https://scratch.mit.edu/projects/{pid}/embed",
        "link": "https://scratch.mit.edu/projects/{pid}",
        "label": "Scratch",
    },
    "turbowarp": {
        "embed": "https://turbowarp.org/{pid}/embed",
        "link": "https://turbowarp.org/{pid}",
        "label": "TurboWarp",
    },
}


def parse_scratch_target(raw: str):
    """Urai isi [SCRATCH] menjadi (provider, project_id) atau None."""
    t = (raw or "").strip()
    if _ID_RE.match(t):
        return ("scratch", t)
    m = _SCRATCH_URL_RE.match(t)
    if m:
        return ("scratch", m.group(1))
    m = _TURBOWARP_URL_RE.match(t)
    if m:
        return ("turbowarp", m.group(1))
    return None


def scratch_embed_html(raw: str, line: int, errors: list) -> str:
    target = parse_scratch_target(raw)
    if target is None:
        errors.append(
            {
                "line": line,
                "message": (
                    "Format [SCRATCH] tidak dikenal. Isi dengan ID proyek (angka saja) "
                    "atau URL resmi scratch.mit.edu/projects/<id> / turbowarp.org/<id>."
                ),
            }
        )
        return ""
    provider, pid = target
    cfg = PROVIDERS[provider]
    embed = cfg["embed"].format(pid=pid)
    link = cfg["link"].format(pid=pid)
    return (
        f'<div class="tc-scratch">'
        f'<iframe src="{embed}" width="485" height="402" frameborder="0" scrolling="no" '
        f'allowfullscreen loading="lazy" title="Proyek Scratch {pid}"></iframe>'
        f'<p class="tc-scratch-caption">▶ Proyek {escape(cfg["label"])} #{pid} — '
        f'<a href="{link}" target="_blank" rel="noreferrer">buka di {escape(cfg["label"])}</a> '
        f"untuk melihat kode & me-remix.</p></div>"
    )


def blocks_html(raw: str) -> str:
    return f'<pre class="scratchblocks">{escape((raw or "").strip())}</pre>'


def sprite_html(raw: str) -> str:
    lines = [ln.strip() for ln in (raw or "").strip().split("\n") if ln.strip()]
    if not lines:
        return ""
    name = escape(lines[0])
    desc = "<br>".join(escape(ln) for ln in lines[1:])
    return (
        f'<div class="tc-sprite"><div class="tc-sprite-name">🐱 Sprite: {name}</div>'
        f'<div class="tc-sprite-desc">{desc}</div></div>'
    )
