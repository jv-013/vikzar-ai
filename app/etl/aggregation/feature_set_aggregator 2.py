"""
Feature Set Aggregation.

An ETL composition layer, not a numbered pipeline stage: sits between
Feature Validation and Publisher solely so Publisher itself can remain
stateless (see docs/development/AGGREGATION_DESIGN.md and
docs/architecture/10_SYSTEM_DECISIONS.md, Decision 030).

Collects one ValidatedFeatureSet per synchronization group and, once
every configured group has at least one queued, assembles them into one
AggregatedFeatureCycle. Never reads, compares, or merges any group's
biomarker values — only pairs already-independent objects by arrival
order, per group.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Callable, Deque, Dict, Sequence, Tuple

from app.etl.feature_validation import ValidatedFeatureSet

from .aggregated_feature_cycle import AggregatedFeatureCycle

logger = logging.getLogger(__name__)

AggregatedFeatureCycleConsumer = Callable[[AggregatedFeatureCycle], None]
"""Invoked with each AggregatedFeatureCycle as it is emitted."""


class FeatureSetAggregator:
    """
    Converts a stream of per-group ValidatedFeatureSets into complete
    AggregatedFeatureCycles.

    Purpose
        Maintain one FIFO queue per configured group_id. Whenever every
        configured group's queue is non-empty, pop the oldest entry
        from each and emit one AggregatedFeatureCycle — FIFO pairing by
        arrival order, not by exact window_start equality (which is not
        guaranteed across groups: each group's Windower independently
        anchors its own first window to its own first-ever frame's
        reference_timestamp).

    Known, documented limitation
        No timeout. If one group stops producing ValidatedFeatureSets
        entirely (e.g. a Smart Pod loses power), this aggregator waits
        forever for it — the other group's real, valid data never
        publishes either. A timeout-based partial-publish was
        considered and deliberately deferred: no validated duration
        exists to justify a specific timeout number, and a
        sometimes-there-sometimes-not per-group presence driven by an
        invented timer adds real complexity for AI to handle. This is
        the same "document the gap, don't fabricate a threshold"
        treatment as contact_duration and FSR402CharacterizedCalibration.

    Idempotency
        handle() only ever accepts a ValidatedFeatureSet and raises
        TypeError immediately, outside the internal try/except, for
        anything else. This aggregator holds even more consequential
        per-group state than Filtering or Windowing (a full FIFO queue,
        not just a running value) — reprocessing or misordering an
        input would desynchronize which ValidatedFeatureSets get paired
        together across groups.
    """

    def __init__(
        self,
        group_ids: Sequence[str],
        on_aggregated: AggregatedFeatureCycleConsumer,
    ) -> None:
        """
        Initialize the aggregator.

        Args:
            group_ids: The synchronization groups to wait for, every
                cycle. Must be non-empty. The same group_id set used to
                construct Synchronizer for this session.
            on_aggregated: Callback invoked with each emitted
                AggregatedFeatureCycle.

        Raises:
            ValueError: If group_ids is empty.
        """
        if not group_ids:
            raise ValueError("FeatureSetAggregator requires at least one group_id.")
        self._group_ids: Tuple[str, ...] = tuple(group_ids)
        self._on_aggregated = on_aggregated
        self._queues: Dict[str, Deque[ValidatedFeatureSet]] = {
            group_id: deque() for group_id in self._group_ids
        }

    def handle(self, validated: ValidatedFeatureSet) -> None:
        """
        Enqueue a single ValidatedFeatureSet, emitting zero or more
        complete AggregatedFeatureCycles.

        This is the entry point wired as FeatureValidator's on_validated
        callback. Data-quality problems (an unconfigured group_id) are
        logged and dropped; a wrong input type is a wiring bug and
        raises immediately.

        Args:
            validated: The feature set to enqueue.

        Raises:
            TypeError: If validated is not a ValidatedFeatureSet.
        """
        if not isinstance(validated, ValidatedFeatureSet):
            raise TypeError(
                f"FeatureSetAggregator.handle() only accepts ValidatedFeatureSet; "
                f"received {type(validated).__name__}."
            )
        try:
            self._handle(validated)
        except Exception:
            logger.exception(
                "feature_set_aggregator.unexpected_error",
                extra={"group_id": validated.raw.group_id},
            )

    def _handle(self, validated: ValidatedFeatureSet) -> None:
        group_id = validated.raw.group_id
        queue = self._queues.get(group_id)
        if queue is None:
            logger.warning(
                "feature_set_aggregator.unconfigured_group",
                extra={"group_id": group_id},
            )
            return

        queue.append(validated)
        self._emit_complete_cycles()

    def _emit_complete_cycles(self) -> None:
        while all(self._queues[group_id] for group_id in self._group_ids):
            groups = {group_id: self._queues[group_id].popleft() for group_id in self._group_ids}
            cycle = AggregatedFeatureCycle(groups=groups)
            self._on_aggregated(cycle)
