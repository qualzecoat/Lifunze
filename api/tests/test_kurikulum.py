"""Tes Batch 4+5 (2026-10-21): info kelas opsional, AI Kurikulum
(generate draf -> simpan -> terapkan jadi pertemuan), dan konteks
kesinambungan pada generate dari pertemuan."""

import json

from tests.conftest import login, make_user
from tests.test_generate_pedagogi import (
    MATERI_2_BAGIAN,
    UNIT_CEK,
    buat_paket_lengkap,
    buat_setting,
)


def fake_ai(monkeypatch, responses, capture=None):
    """Patch chat_completion di KEDUA pemakai (generate & kurikulum)."""
    queue = list(responses)

    def _fake(setting, messages, temperature=0.7):
        if capture is not None:
            capture.append(messages)
        assert queue, "fake AI kehabisan jawaban"
        return queue.pop(0)

    monkeypatch.setattr("app.routers.generate.chat_completion", _fake)
    monkeypatch.setattr("app.routers.kurikulum.chat_completion", _fake)

RENCANA_JSON = json.dumps([
    {"judul": "Pecahan Dasar", "tujuan": "Siswa memahami arti pecahan",
     "konsep": ["pembilang", "penyebut"], "aktivitas": ["studi kasus"], "alur": "Konsep Bertahap"},
    {"judul": "Menyederhanakan", "tujuan": "Siswa bisa menyederhanakan pecahan",
     "konsep": ["FPB"], "aktivitas": ["praktik"], "alur": "Alur Ngawur"},
])


def _kelas(client, csrf, **info):
    r = client.post(
        "/api/v1/subjects",
        json={"nama": "Matematika", **info},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_info_kelas_opsional_tersimpan(client):
    make_user("guru_info", "guru")
    csrf = login(client, "guru_info")
    s = _kelas(client, csrf, jenjang="SD Kelas 5", target_siswa="Anak usia 10-11 tahun",
               tujuan_akhir="Mahir pecahan")
    assert s["jenjang"] == "SD Kelas 5" and s["tujuan_akhir"] == "Mahir pecahan"
    # Kelas polos tetap sah (info tidak diwajibkan).
    s2 = _kelas(client, csrf)
    assert s2["jenjang"] is None and s2["kurikulum"] is None
    # Patch info belakangan.
    r = client.patch(f"/api/v1/subjects/{s2['id']}", json={"jenjang": "SMP"},
                     headers={"x-csrf-token": csrf})
    assert r.json()["jenjang"] == "SMP"


def test_kurikulum_generate_simpan_terapkan(client, monkeypatch):
    make_user("guru_kur", "guru")
    csrf = login(client, "guru_kur")
    buat_setting(client, csrf)
    s = _kelas(client, csrf, jenjang="SD Kelas 5")
    fake_ai(monkeypatch, [RENCANA_JSON])

    r = client.post(
        f"/api/v1/subjects/{s['id']}/kurikulum/generate",
        json={"mode": "nol", "jumlah_pertemuan": 2},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 201 or r.status_code == 200, r.text
    rencana = r.json()["rencana"]
    assert [x["judul"] for x in rencana] == ["Pecahan Dasar", "Menyederhanakan"]
    assert rencana[0]["alur"] == "Konsep Bertahap"
    assert rencana[1]["alur"] is None, "alur tak dikenal harus dinetralkan"

    r = client.put(
        f"/api/v1/subjects/{s['id']}/kurikulum",
        json={"pertemuan": rencana},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200, r.text

    r = client.post(f"/api/v1/subjects/{s['id']}/kurikulum/terapkan",
                    headers={"x-csrf-token": csrf})
    assert r.status_code == 200, r.text
    assert r.json()["dibuat"] == 2
    detail = client.get(f"/api/v1/subjects/{s['id']}").json()
    assert [m["judul"] for m in detail["meetings"]] == ["Pecahan Dasar", "Menyederhanakan"]
    assert detail["meetings"][0]["rencana"]["tujuan"].startswith("Siswa memahami")

    # Terapkan kedua: tidak membuat duplikat.
    r = client.post(f"/api/v1/subjects/{s['id']}/kurikulum/terapkan",
                    headers={"x-csrf-token": csrf})
    assert r.json()["dibuat"] == 0
    detail = client.get(f"/api/v1/subjects/{s['id']}").json()
    assert len(detail["meetings"]) == 2


def test_generate_dari_pertemuan_memakai_konteks_dan_alur_rencana(client, monkeypatch):
    make_user("guru_konteks", "guru")
    csrf = login(client, "guru_konteks")
    buat_setting(client, csrf)
    pack = buat_paket_lengkap(client, csrf)
    s = _kelas(client, csrf, jenjang="SD Kelas 5")
    client.put(
        f"/api/v1/subjects/{s['id']}/kurikulum",
        json={"pertemuan": [
            {"judul": "Pecahan Dasar", "tujuan": "Memahami arti pecahan",
             "konsep": ["pembilang"], "aktivitas": ["studi kasus"], "alur": "Konsep Bertahap"},
            {"judul": "Menyederhanakan", "tujuan": "Bisa menyederhanakan",
             "konsep": ["FPB"], "aktivitas": ["praktik"], "alur": "Konsep Bertahap"},
        ]},
        headers={"x-csrf-token": csrf},
    )
    client.post(f"/api/v1/subjects/{s['id']}/kurikulum/terapkan", headers={"x-csrf-token": csrf})
    detail = client.get(f"/api/v1/subjects/{s['id']}").json()
    m1, m2 = detail["meetings"]
    # Pertemuan 1 sudah punya materi aktual.
    r = client.post(
        f"/api/v1/meetings/{m1['id']}/materials",
        json={"judul": "Pecahan", "teks_mentah": MATERI_2_BAGIAN},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code in (200, 201), r.text

    capture = []
    # Dua tahap aktif (template dari rencana punya bagian cek): materi dulu,
    # lalu unit soal sisipan.
    fake_ai(monkeypatch, [MATERI_2_BAGIAN, UNIT_CEK], capture=capture)
    res = client.post(
        "/api/v1/generate",
        json={
            "kind": "dokumen", "pack_id": pack["id"],
            "brief": {"topik": "Menyederhanakan pecahan", "jenis_dokumen": "materi",
                      "subject_id": s["id"], "meeting_id": m2["id"]},
        },
        headers={"x-csrf-token": csrf},
    )
    assert res.status_code == 201, res.text
    prompt = capture[0][1]["content"]
    assert "KONTEKS KELAS" in prompt
    assert "Bisa menyederhanakan" in prompt  # tujuan rencana pertemuan ini
    assert "Pengertian Pecahan" in prompt  # ringkasan aktual pertemuan 1 (sub-bab)
    # Template ditebak dari alur rencana -> dua tahap aktif (ada bagian cek).
    assert res.json()["template_id"] is not None
    assert "ALUR MENGAJAR" in prompt
