"""Storage abstraction for object and file-based data access."""

from typing import Any, Optional


class Storage:
    """Base class for storage backends."""

    def put(self, key: str, data: Any) -> None:
        raise NotImplementedError

    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError
