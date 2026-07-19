"""
Feature Extraction.

Stage 7 of the ETL pipeline (see docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/FEATURE_EXTRACTION_DESIGN.md).

Computes objective, reproducible numerical features from each Window,
per synchronization group, using stateless, domain-scoped FeatureModule
strategies. Never merges or compares across groups; never classifies,
estimates, or interprets — every feature is a measurable quantity.
Feature Validation (next stage) validates this output; app/etl/publisher
(later) crosses the ETL->AI boundary into RawFeatureVector. Feature
Extraction touches neither.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Mapping

from app.etl.windowing import Window

from .extracted_feature_set import ExtractedFeatureSet
from .feature_module import FeatureModule

logger = logging.getLogger(__name__)

ExtractedFeatureSetConsumer = Callable[[ExtractedFeatureSet], None]
"""Invoked with each ExtractedFeatureSet as it is emitted."""


class Extractor:
    """
    Converts Windows into ExtractedFeatureSets.

    Purpose
        Run every registered FeatureModule against each Window and
        merge their results into one ExtractedFeatureSet, keyed by
        domain name. A domain absent from a module's result (no
        applicable data this window) is omitted entirely, never
        zero-filled.

    Idempotency
        Every FeatureModule is a pure function of its window argument,
        with no state of its own — Feature Extraction is stateless,
        the same as Calibration, not stateful like Filtering or
        Windowing. handle() still checks isinstance(window, Window)
        and raises TypeError immediately, outside the internal
        try/except, for anything else — purely a wiring-bug catcher
        (like Calibration's guard), since there is no per-call state
        here that reprocessing could corrupt.
    """

    def __init__(
        self,
        feature_modules: Mapping[str, FeatureModule],
        on_extracted: ExtractedFeatureSetConsumer,
    ) -> None:
        """
        Initialize the extractor.

        Args:
            feature_modules: FeatureModule to run, keyed by domain name
                (e.g. "motion"). See defaults.default_feature_modules.
            on_extracted: Callback invoked with each emitted
                ExtractedFeatureSet.
        """
        self._feature_modules: Dict[str, FeatureModule] = dict(feature_modules)
        self._on_extracted = on_extracted

    def handle(self, window: Window) -> None:
        """
        Extract features from a single Window.

        This is the entry point wired as Windower's on_window callback.
        Raises immediately for a wrong input type; every other failure
        is logged and the window is dropped.

        Args:
            window: The window to extract features from.

        Raises:
            TypeError: If window is not a Window.
        """
        if not isinstance(window, Window):
            raise TypeError(
                f"Extractor.handle() only accepts Window; received "
                f"{type(window).__name__}."
            )
        try:
            self._handle(window)
        except Exception:
            logger.exception(
                "extractor.unexpected_error",
                extra={"group_id": window.group_id},
            )

    def _handle(self, window: Window) -> None:
        domains: Dict[str, Mapping[str, float]] = {}
        sample_counts: Dict[str, int] = {}
        for domain_name, module in self._feature_modules.items():
            result = module.extract(window)
            if result.features:
                domains[domain_name] = result.features
                sample_counts[domain_name] = result.sample_count

        extracted = ExtractedFeatureSet(
            group_id=window.group_id,
            window_specification_name=window.window_specification_name,
            window_start=window.window_start,
            window_end=window.window_end,
            domains=domains,
            sample_counts=sample_counts,
        )
        self._on_extracted(extracted)
