"""Module documentation."""

from vlooper.persistence.migrations.base import Migration


class CreateTasksStepsTable(Migration):
    """Create the tasks_steps table."""

    @property
    def description(self) -> str:
        return "create_tasks_steps_table"

    def up(self, connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL, -- PENDING, RUNNING, COMPLETED, FAILED
                order_index INTEGER NOT NULL,
                input_data TEXT,
                output_data TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)

    def down(self, connection):
        connection.execute("DROP TABLE IF EXISTS tasks_steps")
