"""Pembacaan unggahan berukuran terbatas (audit #27).

Dulu handler membaca SELURUH file ke memori sebelum memeriksa ukuran —
file raksasa bisa menghabiskan memori server sebelum ditolak. Helper ini
membaca per potongan dan berhenti segera setelah melewati batas.
"""

from fastapi import HTTPException, UploadFile

_CHUNK = 256 * 1024


async def read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    bagian: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Ukuran file melebihi {max_bytes // (1024 * 1024)} MB.",
            )
        bagian.append(chunk)
    return b"".join(bagian)
