"""Compatibility entry point for the modular TMS FastAPI application."""

from pathlib import Path

from .app import config
from .app.api.routes import *  # noqa: F403
from .app.api.routes import app


def configure_paths(*, db_path: Path | None = None, upload_dir: Path | None = None) -> None:
    """Configure isolated SQLite/upload paths for callers that import ``backend.main``."""
    config.configure_paths(db_path=db_path, upload_dir=upload_dir)
