import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


DEFAULT_DOCKER_DATABASE_URL = (
    "postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly"
)


def get_database_url() -> str:
    """
    Return the configured Postgres database URL.
    The application is Postgres-only and will fail fast if no URL is configured.
    """
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    if os.getenv("SMART_ASSEMBLY_DB_BACKEND", "").lower() == "postgres":
        return DEFAULT_DOCKER_DATABASE_URL

    raise RuntimeError(
        "DATABASE_URL is not set. Export a PostgreSQL URL or set "
        "SMART_ASSEMBLY_DB_BACKEND=postgres before starting the app."
    )
