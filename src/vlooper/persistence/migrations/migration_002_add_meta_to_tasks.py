"""Module documentation."""

from vlooper.persistence.migrations.base import Migration


class AddMetaToTasks(Migration):
    """Add meta column to tasks table."""

    @property
    def description(self) -> str:
        return "add_meta_to_tasks"

    def up(self, connection):
        connection.execute("ALTER TABLE tasks ADD COLUMN meta TEXT")

    def down(self, connection):
        # SQLite support for DROP COLUMN is limited in older versions.
        pass
