"""Compatibility entry point for the modular TMS FastAPI application.

The application is assembled by ``backend.app.api.routes``. The explicit
re-exports below preserve the original ``backend.main`` test/import surface
while HTTP adapters live in ``backend.app.api``.
"""

from pathlib import Path

from fastapi import HTTPException

from .app import config
from .app.api.routes import app
from .app.core.permissions import *  # noqa: F403
from .app.core.security import *  # noqa: F403
from .app.db.connection import get_conn
from .app.db.schema import init_db, seed
from .app.models.enums import *  # noqa: F403
from .app.repositories.common import *  # noqa: F403
from .app.schemas import *  # noqa: F403
from .app.services.auth_service import *  # noqa: F403
from .app.services.billing_service import *  # noqa: F403
from .app.services.exception_service import *  # noqa: F403
from .app.services.notification_service import *  # noqa: F403
from .app.services.order_rules import *  # noqa: F403
from .app.services.order_service import *  # noqa: F403
from .app.services.parcel_service import *  # noqa: F403
from .app.services.task_service import *  # noqa: F403


def configure_paths(*, db_path: Path | None = None, upload_dir: Path | None = None) -> None:
    """Configure isolated SQLite/upload paths for callers that import ``backend.main``."""
    config.configure_paths(db_path=db_path, upload_dir=upload_dir)
