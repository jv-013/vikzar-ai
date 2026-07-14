"""Queue abstraction for asynchronous message handling."""

from typing import Any, List


class QueueClient:
    """Base class for queue client implementations."""

    def publish(self, message: Any) -> None:
        raise NotImplementedError

    def consume(self) -> List[Any]:
        raise NotImplementedError
