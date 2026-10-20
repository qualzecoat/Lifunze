"""Konfigurasi Lifunze API — dibaca dari environment variable."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIFUNZE_", env_file=".env", extra="ignore")

    # Database: default SQLite untuk dev lokal tanpa Docker.
    # Di Docker Compose diganti: postgresql+psycopg://lifunze:lifunze@db:5432/lifunze
    database_url: str = "sqlite:///./lifunze-dev.db"

    secret_key: str = "dev-secret-key-ganti-di-production"
    fernet_key: str = ""  # kunci enkripsi API key AI (Fase 1). Harus 32 byte urlsafe base64.

    app_name: str = "lifunze-api"
    debug: bool = False
    # Lingkungan: "dev" (default) atau "production" — production memicu
    # validasi konfigurasi ketat saat startup (lihat validate_production).
    env: str = "dev"

    # Cookie sesi: aktifkan Secure di production (di balik HTTPS/Caddy).
    cookie_secure: bool = False
    # Origin frontend yang diizinkan CORS (dev lokal). Di production satu origin via Caddy.
    cors_origins: list[str] = ["http://localhost:3000"]

    # Penyimpanan lampiran materi (volume lokal; di Docker diarahkan ke volume persisten).
    storage_dir: str = "./storage"
    max_upload_mb: int = 16

    # Admin awal hanya dibuat via seed (Fase 1). Disimpan di env, bukan kode.
    admin_username: str = ""
    admin_password: str = ""


settings = Settings()


def validate_production(s: Settings) -> list[str]:
    """Daftar masalah konfigurasi production; kosong = aman go-live.

    Hanya ditegakkan bila s.env == 'production' (Fase 8 hardening).
    """
    problems: list[str] = []
    if s.env != "production":
        return problems
    if not s.fernet_key:
        problems.append("LIFUNZE_FERNET_KEY wajib diisi di production.")
    if s.secret_key == "dev-secret-key-ganti-di-production" or len(s.secret_key) < 24:
        problems.append("LIFUNZE_SECRET_KEY harus diganti & minimal 24 karakter di production.")
    if not s.cookie_secure:
        problems.append("LIFUNZE_COOKIE_SECURE harus true di production (HTTPS).")
    if not s.database_url.startswith("postgresql"):
        problems.append("Production wajib memakai PostgreSQL (LIFUNZE_DATABASE_URL).")
    if s.admin_username and len(s.admin_password) < 12:
        problems.append("LIFUNZE_ADMIN_PASSWORD minimal 12 karakter di production.")
    return problems
