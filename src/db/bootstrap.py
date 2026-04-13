from .base import Base
from .session import engine


def create_database() -> None:
    """Create all known tables for local bootstrapping."""
    from . import models  # Imported here so metadata is fully registered.

    _ = models
    Base.metadata.create_all(bind=engine)
