"""Uploader abstraction for file delivery to cloud storage."""

from typing import Any


class Uploader:
    """Base class for upload implementations."""

    def upload(self, file_path: str, destination: str) -> Any:
        raise NotImplementedError

    def download(self, source: str, destination: str) -> Any:
        raise NotImplementedError
