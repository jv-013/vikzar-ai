"""
Fixed-size history buffer for FeatureVectors.

Stores the most recent FeatureVectors required
for temporal feature computation.
"""

from collections import deque
from typing import Deque

from app.schemas.feature_vector import FeatureVector


class HistoryBuffer:
    """
    Fixed-size circular buffer for FeatureVectors.
    """

    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self._buffer: Deque[FeatureVector] = deque(maxlen=max_size)

    def add(self, feature_vector: FeatureVector) -> None:
        """
        Add a new FeatureVector.
        If the buffer is full, the oldest
        FeatureVector is automatically removed.
        """
        self._buffer.append(feature_vector)

    def get_all(self) -> list[FeatureVector]:
        """
        Return all FeatureVectors in chronological order.
        """
        return list(self._buffer)

    def latest(self) -> FeatureVector | None:
        """
        Return the newest FeatureVector.
        """
        if not self._buffer:
            return None

        return self._buffer[-1]

    def oldest(self) -> FeatureVector | None:
        """
        Return the oldest FeatureVector.
        """
        if not self._buffer:
            return None

        return self._buffer[0]

    def size(self) -> int:
        """
        Current number of FeatureVectors.
        """
        return len(self._buffer)

    def is_full(self) -> bool:
        """
        Check whether the buffer has reached capacity.
        """
        return len(self._buffer) == self.max_size

    def clear(self) -> None:
        """
        Remove all stored FeatureVectors.
        """
        self._buffer.clear()