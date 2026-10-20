"""Test Fase 7: modul Scratch — tag [SCRATCH], [BLOCKS], [SPRITE]."""

from conftest import login, make_user

from app.tcml import parse_material

MATERI_SCRATCH = """[MATERIAL]
[TITLE]Gerak Sprite[/TITLE]
[SCRATCH]104[/SCRATCH]
[SPRITE]
Kucing
Sprite utama yang digerakkan pemain.
[/SPRITE]
[BLOCKS]
when green flag clicked
move (10) steps
[/BLOCKS]
[/MATERIAL]"""


def test_parse_embed_id_angka():
    res = parse_material(MATERI_SCRATCH)
    assert res["success"], res
    html = res["content"]
    assert 'src="https://scratch.mit.edu/projects/104/embed"' in html
    assert "scratchblocks" in html and "move (10) steps" in html
    assert "tc-sprite" in html and "Kucing" in html


def test_parse_embed_url_scratch_dan_turbowarp():
    res = parse_material("[MATERIAL]\n[SCRATCH]https://scratch.mit.edu/projects/961778897/[/SCRATCH]\n[/MATERIAL]")
    assert res["success"], res
    assert "scratch.mit.edu/projects/961778897/embed" in res["content"]

    res = parse_material("[MATERIAL]\n[SCRATCH]https://turbowarp.org/961778897[/SCRATCH]\n[/MATERIAL]")
    assert res["success"], res
    assert "turbowarp.org/961778897/embed" in res["content"]


def test_embed_jahat_ditolak():
    for jahat in (
        "javascript:alert(1)",
        "https://evil.example.com/projects/1",
        "bukan-url",
        "104; DROP",
    ):
        res = parse_material(f"[MATERIAL]\n[SCRATCH]{jahat}[/SCRATCH]\n[/MATERIAL]")
        assert res["success"] is False, jahat
        assert any("SCRATCH" in e["message"] for e in res["errors"])


def test_blocks_terescape_xss():
    res = parse_material("[MATERIAL]\n[BLOCKS]\nsay <script>alert(1)</script>\n[/BLOCKS]\n[/MATERIAL]")
    assert res["success"], res
    assert "<script>alert(1)</script>" not in res["content"]
    assert "&lt;script&gt;" in res["content"]


def test_modul_dan_preset_scratch_via_api(client):
    make_user("guru1", "guru")
    csrf = login(client, "guru1")

    modules = client.get("/api/v1/packs/modules").json()
    scratch = [m for m in modules if m["slug"] == "scratch"]
    assert scratch and set(scratch[0]["tags"]) == {"SCRATCH", "BLOCKS", "SPRITE"}

    packs = client.get("/api/v1/packs").json()
    kursus = [p for p in packs if p["nama"] == "Kursus Scratch"]
    assert len(kursus) == 1
    detail = client.get(f"/api/v1/packs/{kursus[0]['id']}").json()
    slugs = {m["slug"] for m in detail["modules"]}
    assert "scratch" in slugs

    # contoh pada modul bisa diparse (spec sinkron dengan engine)
    contoh = client.get("/api/v1/tcml/modules").json()
    mod = contoh["scratch"]
    assert mod["contoh"]
    res = parse_material(mod["contoh"][0]["konten"])
    assert res["success"], res


def test_validasi_lapis2_paket_scratch(client):
    guru = make_user("guru1", "guru")
    csrf = login(client, "guru1")
    packs = client.get("/api/v1/packs").json()
    kursus = [p for p in packs if p["nama"] == "Kursus Scratch"][0]

    # impor materi dengan [SCRATCH] via paket Scratch -> valid
    res = client.post(
        "/api/v1/generate/import",
        json={"kind": "materi", "pack_id": kursus["id"], "teks": MATERI_SCRATCH},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    assert res.json()["drafts"][0]["is_valid"] is True

    # paket tanpa modul scratch -> [SCRATCH] melanggar skema paket
    pg = client.post(
        "/api/v1/packs",
        json={"nama": "Tanpa Scratch", "module_slugs": ["inti-materi"], "allowed_roots": ["MATERIAL"]},
        headers={"x-csrf-token": csrf},
    ).json()
    res = client.post(
        "/api/v1/generate/import",
        json={"kind": "materi", "pack_id": pg["id"], "teks": MATERI_SCRATCH},
        headers={"x-csrf-token": csrf},
    )
    assert res.json()["drafts"][0]["is_valid"] is False


def test_lampiran_sb3_di_materi(client):
    guru_id = make_user("guru1", "guru")
    csrf = login(client, "guru1")
    sid = client.post("/api/v1/subjects", json={"nama": "Scratch SD"}, headers={"x-csrf-token": csrf}).json()["id"]
    mid = client.post(f"/api/v1/subjects/{sid}/meetings", json={"judul": "P1"}, headers={"x-csrf-token": csrf}).json()["id"]
    mat = client.post(
        f"/api/v1/meetings/{mid}/materials",
        json={"judul": "Starter", "teks_mentah": MATERI_SCRATCH},
        headers={"x-csrf-token": csrf},
    )
    assert mat.status_code == 201, mat.text
    res = client.post(
        f"/api/v1/materials/{mat.json()['id']}/files",
        files={"file": ("starter.sb3", b"PK\x03\x04 dummy sb3", "application/octet-stream")},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
