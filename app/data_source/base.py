from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseFeatureSource(ABC):
    """
    Abstract base class for all feature sources.

    Every implementation (Synthetic, ETL, Replay, etc.)
    must return one feature vector at a time.
    """

    @abstractmethod
    def connect(self) -> None:
        """
        Initialize the feature source.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Cleanly shut down the feature source.
        """
        pass

    @abstractmethod
    def get_next_feature_vector(self) -> Dict[str, Any]:
        """
        Return the next feature vector.

        Returns
        -------
        Dict[str, Any]
            One feature vector ready for validation.
        """
        pass