from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.bootstrap import create_database
from src.db.session import get_database_url


if __name__ == "__main__":
    create_database()
    print(f"PostgreSQL schema initialized at {get_database_url()}")
