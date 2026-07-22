"""Deterministic stratification of immutable ground-truth evidence."""

from __future__ import annotations

from collections import defaultdict

from .contracts import EvaluationSlice, GroundTruthRow, SliceDimension


def slice_ground_truth_rows(
    rows: tuple[GroundTruthRow, ...],
) -> tuple[tuple[EvaluationSlice, tuple[GroundTruthRow, ...]], ...]:
    """Group truth rows by every available supported evidence dimension."""

    groups: dict[tuple[SliceDimension, str], list[GroundTruthRow]] = defaultdict(list)
    for row in rows:
        groups[(SliceDimension.PLAYER, row.player_id)].append(row)
        groups[(SliceDimension.SESSION, row.session_id)].append(row)
        groups[(SliceDimension.DATASET_SPLIT, row.dataset_split.value)].append(row)
        if row.position is not None:
            groups[(SliceDimension.POSITION, row.position)].append(row)
        if row.drill_id is not None:
            groups[(SliceDimension.DRILL, row.drill_id)].append(row)
    return tuple(
        (EvaluationSlice(dimension=dimension, value=value), tuple(group_rows))
        for (dimension, value), group_rows in sorted(groups.items(), key=lambda item: (item[0][0].value, item[0][1]))
    )
