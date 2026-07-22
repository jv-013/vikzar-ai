"""
Cloud Repository Interface.

This module provides a single entry point
for cloud operations.
"""


class CloudRepository:
    """
    Base repository used by the AI pipeline.

    The underlying implementation can later
    use AWS, Azure, GCP or local storage
    without changing the AI.
    """

    def upload_feature_vector(self, feature_vector):
        raise NotImplementedError

    def upload_prediction(self, prediction):
        raise NotImplementedError

    def upload_risk_scores(self, risk_scores):
        raise NotImplementedError

    def upload_session(self, session_data):
        raise NotImplementedError