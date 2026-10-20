"""Klien AI generik OpenAI-compatible untuk fitur Generate (Fase 5).

Satu fungsi chat_completion dipakai generate & perbaikan draf; kegagalan
apa pun diterjemahkan menjadi ProviderError berpesan jelas (Bahasa Indonesia)
agar bisa ditampilkan apa adanya ke guru.
"""

import httpx

from .models import AiSetting
from .security import decrypt_secret


class ProviderError(Exception):
    """Kegagalan memanggil provider AI (koneksi, status HTTP, format respons)."""


def chat_completion(setting: AiSetting, messages: list[dict], temperature: float = 0.7) -> str:
    try:
        api_key = decrypt_secret(setting.api_key_encrypted)
    except Exception:
        raise ProviderError(
            "API key pada Pengaturan AI tidak bisa dibaca. Simpan ulang Pengaturan AI Anda."
        )
    if not setting.model:
        raise ProviderError(
            "Model belum dipilih pada Pengaturan AI. Buka Pengaturan AI dan pilih model dulu."
        )
    url = setting.base_url.rstrip("/") + "/chat/completions"
    try:
        with httpx.Client(timeout=180) as client:
            resp = client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": setting.model,
                    "messages": messages,
                    "temperature": temperature,
                },
            )
    except httpx.HTTPError as e:
        raise ProviderError(f"Gagal menghubungi provider AI: {e}")
    if resp.status_code != 200:
        raise ProviderError(
            f"Provider AI menjawab {resp.status_code}: {resp.text[:300]}"
        )
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError(
            "Respons provider AI tidak berformat chat completion yang dikenal."
        )
