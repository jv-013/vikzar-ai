from pydantic import BaseModel

from .feature_vector import FeatureVector
from .personalized_features import PersonalizedFeatures
from .temporal_features import TemporalFeatures
from .biomechanics_features import BiomechanicsFeatures
from .reliability_features import ReliabilityFeatures


class EnhancedFeatureVector(BaseModel):
    """
    AI-enhanced version of the original FeatureVector.
    """

    raw: FeatureVector

    personalized: PersonalizedFeatures

    temporal: TemporalFeatures

    biomechanics: BiomechanicsFeatures

    reliability: ReliabilityFeatures