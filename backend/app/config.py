"""Runtime configuration for the SQLite MVP application."""

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND_DIR / "tms.db"
UPLOAD_DIR = Path("/tmp/tms_uploads")
TOKEN_SECRET = "tms-dev-secret"
TOKEN_TTL_HOURS = 12
PBKDF2_ROUNDS = 120_000


def configure_paths(*, db_path: Path | None = None, upload_dir: Path | None = None) -> None:
    """Override local paths for isolated tests without changing production defaults."""
    global DB_PATH, UPLOAD_DIR
    if db_path is not None:
        DB_PATH = db_path
    if upload_dir is not None:
        UPLOAD_DIR = upload_dir
