"""Pembantu notifikasi (Fase 6).

Satu fungsi kecil dipakai semua produsen notifikasi (pengumuman, kuis baru,
attempt masuk, nilai keluar). Tidak commit — pemanggil yang commit agar
notifikasi satu transaksi dengan peristiwa pemicunya.
"""

from sqlalchemy.orm import Session

from .models import Notification


def notify(db: Session, user_ids, tipe: str, payload: dict) -> None:
    seen: set[int] = set()
    for uid in user_ids:
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        db.add(Notification(user_id=uid, tipe=tipe, payload=payload))
