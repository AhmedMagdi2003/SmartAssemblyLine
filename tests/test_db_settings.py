import unittest
from unittest.mock import patch

from src.db.settings import (
    DEFAULT_DOCKER_DATABASE_URL,
    get_database_url,
)


class DatabaseSettingsTests(unittest.TestCase):
    def test_default_docker_url_points_to_local_postgres(self):
        self.assertEqual(
            DEFAULT_DOCKER_DATABASE_URL,
            "postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly",
        )

    def test_get_database_url_uses_explicit_value(self):
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}, clear=True):
            self.assertEqual(get_database_url(), "postgresql://example")

    def test_get_database_url_uses_docker_default_when_requested(self):
        with patch.dict("os.environ", {"SMART_ASSEMBLY_DB_BACKEND": "postgres"}, clear=True):
            self.assertEqual(get_database_url(), DEFAULT_DOCKER_DATABASE_URL)

    def test_get_database_url_requires_postgres_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                get_database_url()


if __name__ == "__main__":
    unittest.main()
