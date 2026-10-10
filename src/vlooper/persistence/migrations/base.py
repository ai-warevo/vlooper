from abc import ABC, abstractmethod

class Migration(ABC):
    """Base class for all migrations."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Unique description of the migration."""
        pass

    @abstractmethod
    def up(self, connection):
        """Apply the migration changes."""
        pass

    @abstractmethod
    def down(self, connection):
        """Revert the migration changes."""
        pass
