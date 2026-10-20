from fastapi.testclient import TestClient
from app.main import app


def test_health():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_parse_content_material():
    client = TestClient(app)
    teks = "[MATERIAL]\n[TITLE]Halo[/TITLE]\n[PARAGRAPH]Tes[/PARAGRAPH]\n[/MATERIAL]"
    res = client.post("/api/v1/parse/content", json={"teks": teks, "jenis": "material"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert '<h1 class="tc-title">Halo</h1>' in body["content"]


def test_parse_content_invalid():
    client = TestClient(app)
    teks = "[MATERIAL]\n[TITLE]Tidak ditutup\n[/MATERIAL]"
    res = client.post("/api/v1/parse/content", json={"teks": teks, "jenis": "material"})
    body = res.json()
    assert body["success"] is False
    assert len(body["errors"]) > 0


def test_tcml_modules():
    client = TestClient(app)
    res = client.get("/api/v1/tcml/modules")
    assert res.status_code == 200
    mods = res.json()
    assert "inti-materi" in mods
    assert "kuis-pg" in mods
