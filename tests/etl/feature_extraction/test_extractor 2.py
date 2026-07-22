"""Unit tests for Extractor."""

from __future__ import annotations

from typing import List

import pytest

from app.etl.calibration import CalibratedChannel, PhysicalUnit
from app.etl.feature_extraction import ExtractedFeatureSet, Extractor
from app.etl.feature_extraction.defaults import default_feature_modules

from .helpers import make_filtered_frame, make_filtered_reading, make_motion_frame, make_window


def _extractor(on_extracted, feature_modules=None) -> Extractor:
    modules = feature_modules if feature_modules is not None else default_feature_modules()
    return Extractor(feature_modules=modules, on_extracted=on_extracted)


def test_merges_domains_from_all_applicable_modules() -> None:
    sets: List[ExtractedFeatureSet] = []
    extractor = _extractor(sets.append)
    frame = make_filtered_frame(
        reference_timestamp=0.0,
        readings={
            "primary_motion": make_filtered_reading(
                filtered_channels={
                    "accel_x": CalibratedChannel(3.0, PhysicalUnit.METERS_PER_SECOND_SQUARED),
                    "accel_y": CalibratedChannel(4.0, PhysicalUnit.METERS_PER_SECOND_SQUARED),
                    "accel_z": CalibratedChannel(0.0, PhysicalUnit.METERS_PER_SECOND_SQUARED),
                }
            ),
            "emg": make_filtered_reading(
                device_id="emg_band",
                filtered_channels={"quadriceps": CalibratedChannel(5.0, PhysicalUnit.VOLTS)},
            ),
        },
    )
    window = make_window([frame])

    extractor.handle(window)

    assert len(sets) == 1
    assert "motion" in sets[0].domains
    assert "muscle" in sets[0].domains
    assert sets[0].sample_counts["motion"] == 1
    assert sets[0].sample_counts["muscle"] == 1


def test_omits_domains_with_no_applicable_data() -> None:
    sets: List[ExtractedFeatureSet] = []
    extractor = _extractor(sets.append)
    # motion_frame's default reading has accel but no fsr/emg channels.
    window = make_window([make_motion_frame(0.0, accel=(1.0, 0.0, 0.0))])

    extractor.handle(window)

    assert "motion" in sets[0].domains
    assert "pressure" not in sets[0].domains
    assert "muscle" not in sets[0].domains
    # sample_counts mirrors domains' keys exactly
    assert set(sets[0].sample_counts.keys()) == {"motion"}


def test_empty_window_produces_empty_domains() -> None:
    sets: List[ExtractedFeatureSet] = []
    extractor = _extractor(sets.append)
    window = make_window(frames=[])

    extractor.handle(window)

    assert sets[0].domains == {}
    assert sets[0].sample_counts == {}


def test_preserves_window_provenance() -> None:
    sets: List[ExtractedFeatureSet] = []
    extractor = _extractor(sets.append)
    window = make_window(
        [make_motion_frame(0.0)],
        group_id="right_lower_limb",
        window_specification_name="secondary",
        window_start=500.0,
        window_end=1500.0,
    )

    extractor.handle(window)

    assert sets[0].group_id == "right_lower_limb"
    assert sets[0].window_specification_name == "secondary"
    assert sets[0].window_start == 500.0
    assert sets[0].window_end == 1500.0


def test_handle_raises_type_error_for_non_window_input() -> None:
    extractor = _extractor(lambda feature_set: None)

    with pytest.raises(TypeError):
        extractor.handle("not a window")  # type: ignore[arg-type]


def test_handle_raises_type_error_for_an_extracted_feature_set_fed_back_in() -> None:
    sets: List[ExtractedFeatureSet] = []
    extractor = _extractor(sets.append)
    extractor.handle(make_window([make_motion_frame(0.0)]))
    assert sets

    with pytest.raises(TypeError):
        extractor.handle(sets[0])  # type: ignore[arg-type]


def test_handle_never_raises_when_a_module_raises_internally() -> None:
    class ExplodingModule:
        def extract(self, window):
            raise RuntimeError("simulated feature module failure")

    sets: List[ExtractedFeatureSet] = []
    extractor = _extractor(sets.append, feature_modules={"broken": ExplodingModule()})

    extractor.handle(make_window([make_motion_frame(0.0)]))  # must not raise

    assert sets == []


def test_deterministic_across_repeated_calls() -> None:
    sets: List[ExtractedFeatureSet] = []
    extractor = _extractor(sets.append)
    window = make_window([make_motion_frame(0.0, accel=(3.0, 4.0, 0.0))])

    extractor.handle(window)
    extractor.handle(window)

    assert sets[0].domains == sets[1].domains
