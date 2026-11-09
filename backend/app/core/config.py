"""Central configuration for The Umidasu backend.

All values are overridable via environment variables so the startup script
(execute.sh) can configure host/port/limits without editing source.
"""
from __future__ import annotations

import os
from pathlib import Path


class Settings:
    APP_NAME: str = "The Umidasu"
    APP_VERSION: str = "1.0.0"
    APP_AUTHOR: str = "TENETx0"

    # Network — bind to loopback only unless explicitly overridden.
    HOST: str = os.environ.get("UMIDASU_HOST", "127.0.0.1")
    PORT: int = int(os.environ.get("UMIDASU_PORT", "8420"))

    # Storage
    BASE_DIR: Path = Path(os.environ.get("UMIDASU_DATA_DIR", str(Path.home() / ".umidasu"))).resolve()
    ORIGINALS_DIR: Path = BASE_DIR / "originals"
    WORKING_DIR: Path = BASE_DIR / "working"
    OUTPUT_DIR: Path = BASE_DIR / "output"
    DB_PATH: Path = BASE_DIR / "umidasu.db"

    # Upload limits
    MAX_UPLOAD_BYTES: int = int(os.environ.get("UMIDASU_MAX_UPLOAD_MB", "512")) * 1024 * 1024
    UPLOAD_CHUNK_SIZE: int = 1024 * 1024  # 1 MiB streaming chunks

    # Parsing resource limits
    PARSER_TIMEOUT_SECONDS: int = int(os.environ.get("UMIDASU_PARSER_TIMEOUT", "30"))
    STRINGS_MIN_LENGTH: int = 4
    STRINGS_MAX_RESULTS: int = 5000
    HEX_PREVIEW_BYTES: int = 4096

    # Session retention — original + working files are deleted after this
    # many hours of inactivity by the cleanup sweep documented in storage.
    RETENTION_HOURS: int = int(os.environ.get("UMIDASU_RETENTION_HOURS", "24"))

    def ensure_dirs(self) -> None:
        for d in (self.BASE_DIR, self.ORIGINALS_DIR, self.WORKING_DIR, self.OUTPUT_DIR):
            d.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(d, 0o700)
            except OSError:
                pass


settings = Settings()
settings.ensure_dirs()
