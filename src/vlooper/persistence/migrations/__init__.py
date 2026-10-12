"""Module documentation."""

from vlooper.persistence.migrations.migration_001_create_tasks_table import (
    CreateTasksTable,
)
from vlooper.persistence.migrations.migration_002_add_meta_to_tasks import (
    AddMetaToTasks,
)
from vlooper.persistence.migrations.migration_003_create_tasks_steps_table import (
    CreateTasksStepsTable,
)

MIGRATIONS = [
    CreateTasksTable(),
    AddMetaToTasks(),
    CreateTasksStepsTable(),
]
