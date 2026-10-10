from vlooper.persistence.migrations.base import Migration

class CreateTasksTable(Migration):
    """Initial migration to create the tasks table."""

    @property
    def description(self) -> str:
        return "create_tasks_table"

    def up(self, connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL, -- ISSUE or PR
                repo_full_name TEXT NOT NULL,
                repo_url TEXT NOT NULL,
                issue_number INTEGER,
                branch_name TEXT NOT NULL,
                status TEXT NOT NULL, -- PENDING, CLAIMED, COMPLETED, FAILED
                retries INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def down(self, connection):
        connection.execute("DROP TABLE IF EXISTS tasks")
