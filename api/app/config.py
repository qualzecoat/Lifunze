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

    # Admin awal hanya dibuat via seed (Fase 1). Disimpan di env, bukan kode.
    admin_username: str = ""
    admin_password: str = ""


settings = Settings()
