"""Canonical configuration and environment snapshots for offline experiments."""

from __future__ import annotations

import importlib.metadata
import platform
import sys
from collections.abc import Mapping

from .contracts import ExecutionEnvironment, MetadataValue


def canonical_metadata(values: Mapping[str, str | int | float | bool | None]) -> tuple[MetadataValue, ...]:
    """Convert scalar configuration mappings into immutable sorted metadata."""

    return tuple(MetadataValue(name=name, value=value) for name, value in sorted(values.items()))


class EnvironmentCollector:
    """Collect explicitly named dependency versions without cloud or runtime access."""

    def collect(
        self,
        *,
        application_version: str,
        dependency_names: tuple[str, ...],
    ) -> ExecutionEnvironment:
        """Return the local software snapshot for a run event."""

        versions = {
            dependency: self._version_for(dependency)
            for dependency in sorted(set(dependency_names))
        }
        return ExecutionEnvironment(
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            application_version=application_version,
            dependency_versions=canonical_metadata(versions),
        )

    @staticmethod
    def _version_for(dependency: str) -> str:
        try:
            return importlib.metadata.version(dependency)
        except importlib.metadata.PackageNotFoundError:
            return "not-installed"
