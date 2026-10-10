import sqlite3

from vlooper.infra.logger import get_logger
from vlooper.persistence.migrations.base import Migration

logger = get_logger(__name__)


class DBMigrator:
    """Handles database migrations for SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def migrate(self, migrations: list[Migration], direction: str = "up"):
        """
        Runs pending migrations in the given direction ("up" or "down").
        """
        with self._get_connection() as conn:
            # Ensure the migrations table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            if direction == "up":
                self._run_up(conn, migrations)
            elif direction == "down":
                self._run_down(conn, migrations)
            else:
                raise ValueError("Direction must be 'up' or 'down'")

    def _run_up(self, conn, migrations: list[Migration]):
        # Get already applied migrations
        cursor = conn.execute("SELECT description FROM _migrations")
        applied_migrations = {row[0] for row in cursor.fetchall()}

        for migration in migrations:
            if migration.description not in applied_migrations:
                logger.info("Applying migration (up): %s", migration.description)
                try:
                    migration.up(conn)
                    conn.execute(
                        "INSERT INTO _migrations (description) VALUES (?)",
                        (migration.description,),
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.error(
                        "Failed to apply migration '%s' (up): %s",
                        migration.description,
                        e,
                    )
                    raise RuntimeError(
                        f"Failed to apply migration '{migration.description}' (up): {e}"
                    ) from e

    def _run_down(self, conn, migrations: list[Migration]):
        # Get applied migrations in reverse order for rolling back
        cursor = conn.execute("SELECT description FROM _migrations ORDER BY id DESC")
        applied_descriptions = [row[0] for row in cursor.fetchall()]

        for migration in migrations:
            if migration.description in applied_descriptions:
                logger.info("Reverting migration (down): %s", migration.description)
                try:
                    migration.down(conn)
                    conn.execute(
                        "DELETE FROM _migrations WHERE description = ?",
                        (migration.description,),
                    )
                    conn.commit()
                    # Remove from the list of things we've processed in this loop to allow correct ordering if migrations are provided out of order
                    applied_descriptions.remove(migration.description)
                except Exception as e:
                    conn.rollback()
                    logger.error(
                        "Failed to revert migration '%s' (down): %s",
                        migration.description,
                        e,
                    )
                    raise RuntimeError(
                        f"Failed to revert migration '{migration.description}' (down): {e}"
                    ) from e
