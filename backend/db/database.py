"""SQLite bootstrap using numbered SQL migrations."""

import sqlite3
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def initialize_database(database_path: Path) -> None:
    """Apply each unapplied migration in filename order."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = int(migration.name.split("_", maxsplit=1)[0])
            if version in applied:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                (version, migration.name),
            )

