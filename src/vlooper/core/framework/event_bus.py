from typing import Any, Callable, Dict, List
import logging

# Set up a basic logger for the event bus to report subscriber errors
logger = logging.getLogger(__name__)

class EventBus:
    """
    A decoupled, synchronous event bus that facilitates reactive updates 
    and logging triggers throughout the system.
    It allows components to subscribe to events and emit them without direct coupling.
    """
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event_name: str, callback: Callable[[Any], None]) -> None:
        """Registers a callback for a specific event name."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)

    def emit(self, event_name: str, data: Any) -> None:
        """
        Emits an event to all subscribed callbacks. 
        Failures in individual subscribers are caught and logged to ensure that 
        the core pipeline execution remains uninterrupted by UI or logging errors.
        """
        logger.debug("Emitting event '%s' with data: %s", event_name, data)
        if event_name not in self._subscribers:
            return

        for callback in self._subscribers[event_name]:
            try:
                callback(data)
            except Exception as e:
                # Critical: Prevent subscriber failures from crashing the core pipeline.
                logger.error(f"Error in EventBus subscriber for event '{event_name}': {e}", exc_info=True)
