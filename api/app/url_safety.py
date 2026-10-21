"""Pagar SSRF untuk base URL provider AI (audit #12).

Base URL AI memang boleh kustom (fitur generik OpenAI-compatible), tetapi
server tidak boleh diarahkan ke dirinya sendiri atau jaringan internal:
- saat base URL disimpan: skema wajib http/https, tanpa kredensial di URL,
  tanpa host localhost / domain .local, dan literal IP wajib alamat global;
- tepat sebelum request keluar: hostname di-resolve dan SEMUA hasil alamat
  wajib global (menangkap domain yang menunjuk IP privat/loopback/link-local,
  termasuk 169.254.169.254 metadata cloud).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """Base URL tidak aman / tidak valid untuk dipanggil dari server."""


def _cek_ip_literal(host: str) -> None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # bukan literal IP — pemeriksaan resolve dilakukan sebelum request
    if not ip.is_global:
        raise UnsafeUrlError(
            "Base URL menunjuk alamat IP non-publik (privat/loopback/internal), yang tidak diizinkan."
        )


def normalize_ai_base_url(raw: str) -> str:
    """Validasi bentuk base URL saat disimpan; kembalikan bentuk bersih."""
    base = (raw or "").strip().rstrip("/")
    if not base:
        raise UnsafeUrlError("Base URL wajib diisi.")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError("Base URL wajib memakai http:// atau https://.")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("Base URL tidak boleh memuat username/password.")
    if parsed.query or parsed.fragment:
        raise UnsafeUrlError("Base URL tidak boleh memuat query/fragment.")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeUrlError("Base URL tidak memiliki host yang valid.")
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        raise UnsafeUrlError("Base URL tidak boleh menunjuk localhost / jaringan lokal (.local).")
    try:
        _ = parsed.port
    except ValueError:
        raise UnsafeUrlError("Port pada base URL tidak valid.")
    _cek_ip_literal(host)
    return base


def assert_public_target(url: str) -> None:
    """Periksa TUJUAN AKHIR tepat sebelum request keluar (anti-SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError("URL tujuan wajib http/https.")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeUrlError("URL tujuan tidak memiliki host yang valid.")
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        raise UnsafeUrlError("URL tujuan menunjuk localhost / jaringan lokal.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        _cek_ip_literal(host)
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UnsafeUrlError(f"Host {host} tidak dapat di-resolve.")
    alamat = {info[4][0] for info in infos}
    if not alamat:
        raise UnsafeUrlError(f"Host {host} tidak memiliki alamat IP.")
    for addr in alamat:
        ip = ipaddress.ip_address(addr)
        if not ip.is_global:
            raise UnsafeUrlError(
                f"Host {host} menunjuk alamat non-publik ({addr}); request diblokir demi keamanan server."
            )
