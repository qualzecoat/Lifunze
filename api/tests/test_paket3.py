"""Test penyempurnaan Paket Parser (2026-10-20): metadata per tag,
pilihan tag (tag_pilihan), pratinjau spec, dan meja uji."""

from app.tcml import parse_material
from app.tcml.quiz import parse_quiz_v2
from app.tcml.registry import MODULES
from tests.conftest import login, make_user

SUBSET = {"inti-materi": ["TITLE", "PARAGRAPH"]}

DOC_OK = "[MATERIAL]\n[TITLE]Halo[/TITLE]\n[PARAGRAPH]Isi biasa.[/PARAGRAPH]\n[/MATERIAL]"
DOC_WARNING = "[MATERIAL]\n[TITLE]Halo[/TITLE]\n[WARNING]Awas![/WARNING]\n[/MATERIAL]"


def _guru(client, username="guru1"):
    make_user(username, "guru")
    return login(client, username)


def buat_paket_tag(client, csrf, tag_pilihan=SUBSET, nama="Paket Tag"):
    slugs = list(tag_pilihan.keys())
    res = client.post(
        "/api/v1/packs",
        json={"nama": nama, "module_slugs": slugs, "tag_pilihan": tag_pilihan},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- registry
def test_semua_tag_punya_metadata_dan_contoh_valid():
    for slug, mod in MODULES.items():
        meta = mod.get("tags_meta", {})
        assert set(meta.keys()) == set(mod["tags"]), f"tags_meta {slug} tidak lengkap"
        for tag, tm in meta.items():
            assert tm["nama"] and tm["desc"] and tm["spec"], f"{slug}:{tag}"
            doc = tm["contoh"]
            assert doc.strip(), f"contoh kosong {slug}:{tag}"
            if tm["jenis"] == "material":
                res = parse_material(doc)
                assert res["success"], f"contoh {slug}:{tag} gagal parse: {res['errors']}"
            else:
                tipe = "pilihan_ganda" if tm["jenis"] == "kuis-pg" else "teks"
                res = parse_quiz_v2(doc, expected_type=tipe)
                assert res["success"], f"contoh {slug}:{tag} gagal parse: {res['errors']}"


def test_modules_endpoint_memuat_tags_meta(client):
    _guru(client)
    mods = client.get("/api/v1/packs/modules").json()
    assert len(mods) == 8
    inti = next(m for m in mods if m["slug"] == "inti-materi")
    assert inti["ikon"]
    title = next(t for t in inti["tags_meta"] if t["tag"] == "TITLE")
    assert title["nama"] == "Judul Dokumen"
    assert title["wajib"] is True
    assert "[TITLE]" in title["contoh"]
    assert inti["examples"] and inti["examples"][0]["jenis"] == "material"


# ------------------------------------------------------------- tag_pilihan
def test_buat_paket_dengan_tag_pilihan(client):
    csrf = _guru(client)
    pack = buat_paket_tag(client, csrf)
    assert pack["tag_pilihan"] == SUBSET
    assert [m["slug"] for m in pack["modules"]] == ["inti-materi"]
    assert "MATERIAL" in pack["allowed_roots"]


def test_tag_pilihan_tidak_dikenal_400(client):
    csrf = _guru(client)
    res = client.post(
        "/api/v1/packs",
        json={
            "nama": "Rusak",
            "module_slugs": ["inti-materi"],
            "tag_pilihan": {"inti-materi": ["TIDAK_ADA"]},
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 400


def test_paket_klasik_tetap_null(client):
    csrf = _guru(client)
    res = client.post(
        "/api/v1/packs",
        json={"nama": "Klasik", "module_slugs": ["inti-materi"]},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201
    assert res.json()["tag_pilihan"] is None


def test_fork_mempertahankan_tag_pilihan(client):
    csrf = _guru(client)
    pack = buat_paket_tag(client, csrf)
    res = client.post(
        f"/api/v1/packs/{pack['id']}/fork", headers={"x-csrf-token": csrf}
    )
    assert res.status_code == 201
    assert res.json()["tag_pilihan"] == SUBSET


# --------------------------------------------------------- pratinjau & uji
def test_preview_spec_mengikuti_pilihan_tag(client):
    csrf = _guru(client)
    res = client.post(
        "/api/v1/packs/preview-spec",
        json={"module_slugs": ["inti-materi"], "tag_pilihan": SUBSET},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    data = res.json()
    assert "[TITLE]" in data["spec"]
    assert "[WARNING]" not in data["spec"]
    assert data["karakter"] == len(data["spec"])


def test_preview_spec_klasik_memuat_semua_tag(client):
    csrf = _guru(client)
    res = client.post(
        "/api/v1/packs/preview-spec",
        json={"module_slugs": ["inti-materi"]},
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    assert "[WARNING]" in res.json()["spec"]


def test_meja_uji_menolak_tag_di_luar_pilihan(client):
    csrf = _guru(client)
    res = client.post(
        "/api/v1/packs/test",
        json={
            "kind": "materi",
            "teks": DOC_WARNING,
            "module_slugs": ["inti-materi"],
            "tag_pilihan": SUBSET,
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 200
    out = res.json()
    assert out["valid"] is False
    assert any("WARNING" in e["message"] for e in out["errors"])


def test_meja_uji_meloloskan_tag_pilihan(client):
    csrf = _guru(client)
    res = client.post(
        "/api/v1/packs/test",
        json={
            "kind": "materi",
            "teks": DOC_OK,
            "module_slugs": ["inti-materi"],
            "tag_pilihan": SUBSET,
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.json()["valid"] is True


def test_meja_uji_klasik_meloloskan_warning(client):
    csrf = _guru(client)
    res = client.post(
        "/api/v1/packs/test",
        json={"kind": "materi", "teks": DOC_WARNING, "module_slugs": ["inti-materi"]},
        headers={"x-csrf-token": csrf},
    )
    assert res.json()["valid"] is True


def test_meja_uji_kuis_pg_tanpa_options_ditolak_untuk_paket_subset(client):
    csrf = _guru(client)
    doc = (
        "[QUIZ]\n[TYPE]pilihan_ganda[/TYPE]\n[QUESTION 1]\n"
        "[QUESTION]Satu tambah satu?[/QUESTION]\n[ANSWER]B[/ANSWER]\n[/QUESTION 1]\n[/QUIZ]"
    )
    subset_pg = {"kuis-pg": ["TYPE", "QUESTION_BLOCK", "QUESTION", "ANSWER"]}
    res = client.post(
        "/api/v1/packs/test",
        json={
            "kind": "kuis_pg",
            "teks": doc,
            "module_slugs": ["kuis-pg"],
            "tag_pilihan": subset_pg,
        },
        headers={"x-csrf-token": csrf},
    )
    # Dokumen memakai tag sesuai pilihan (OPTIONS memang tidak dipakai di
    # dokumen ini) — tetapi sintaks kuis PG tanpa OPTIONS harus gagal lapis 1.
    assert res.json()["valid"] is False
