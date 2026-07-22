"""Unit and integration tests for leakage-safe dataset construction."""

from __future__ import annotations

import pytest

from app.dataset_builder import DatasetBuildSpec, DatasetBuilder
from app.dataset_builder.exceptions import DatasetInputError
from app.schemas.domain_biomarkers import DomainBiomarkers

from .helpers import make_verified_session


SPEC = DatasetBuildSpec(
    dataset_name="synthetic-emg-training",
    target_metric_names=("quadriceps_rms", "hamstring_rms"),
)


def test_builds_direct_measured_targets_and_smart_pod_features_only() -> None:
    """Phase 3 keeps measured EMG out of inputs and exposes it only as targets."""

    result = DatasetBuilder().build([make_verified_session()], SPEC)
    example = result.examples[0]

    assert result.dataset.example_count == 1
    assert result.dataset.feature_schema.feature_names == (
        "feature__motion__peak_resultant_acceleration",
    )
    assert result.dataset.feature_schema.target_names == (
        "target__quadriceps_rms",
        "target__hamstring_rms",
    )
    assert {item.name for item in example.features} == {"feature__motion__peak_resultant_acceleration"}
    assert {item.name for item in example.targets} == {
        "target__quadriceps_rms",
        "target__hamstring_rms",
    }


def test_rejects_window_missing_a_requested_direct_measurement_target() -> None:
    """A model dataset cannot silently train from partially labelled windows."""

    session = make_verified_session()
    incomplete = session.model_copy(update={"labels": (session.labels[0],)})

    with pytest.raises(DatasetInputError, match="missing a requested"):
        DatasetBuilder().build([incomplete], SPEC)


def test_rejects_requested_label_with_wrong_source_vector_provenance() -> None:
    """Target provenance must point to the same accepted Smart Pod window."""

    session = make_verified_session()
    malformed_label = session.labels[0].model_copy(update={"source_feature_vector_id": "wrong-source"})
    malformed = session.model_copy(update={"labels": (malformed_label, session.labels[1])})

    with pytest.raises(DatasetInputError, match="source does not match"):
        DatasetBuilder().build([malformed], SPEC)


def test_rejects_inconsistent_smart_pod_feature_schema() -> None:
    """Missing features are rejected rather than imputed during dataset build."""

    first = make_verified_session(capture_session_id="capture-1")
    second = make_verified_session(capture_session_id="capture-2", session_id="training-2")
    window = second.aligned_windows[0]
    motion = window.smart_pod_features["motion"]
    changed_motion = DomainBiomarkers(
        biomarkers={**motion.biomarkers, "extra_metric": 1.0},
        quality={**motion.quality, "extra_metric": next(iter(motion.quality.values()))},
    )
    changed_window = window.model_copy(
        update={"smart_pod_features": {**window.smart_pod_features, "motion": changed_motion}}
    )
    second = second.model_copy(update={"aligned_windows": (changed_window,)})

    with pytest.raises(DatasetInputError, match="same Smart Pod feature schema"):
        DatasetBuilder().build([first, second], SPEC)


def test_grouped_split_never_separates_the_same_player_session() -> None:
    """Two verified captures from one player/session always receive one split."""

    first = make_verified_session(capture_session_id="capture-a", session_id="shared-session")
    second = make_verified_session(capture_session_id="capture-b", session_id="shared-session")
    result = DatasetBuilder().build([first, second], SPEC)

    assert len({example.split for example in result.examples}) == 1
    assert len(result.dataset.split_memberships) == 1


def test_split_never_separates_one_player_or_one_shared_session() -> None:
    """Split components protect both player history and collective sessions."""

    same_player_first = make_verified_session(
        capture_session_id="capture-player-a",
        player_id="player-a",
        session_id="session-1",
    )
    same_player_second = make_verified_session(
        capture_session_id="capture-player-b",
        player_id="player-a",
        session_id="session-2",
    )
    same_session_other_player = make_verified_session(
        capture_session_id="capture-player-c",
        player_id="player-b",
        session_id="session-2",
    )

    result = DatasetBuilder().build(
        [same_player_first, same_player_second, same_session_other_player],
        SPEC,
    )

    assert len({example.split for example in result.examples}) == 1
    assert len({membership.split for membership in result.dataset.split_memberships}) == 1
