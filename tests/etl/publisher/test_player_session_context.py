"""Unit tests for PlayerSessionContext."""

from __future__ import annotations

import pytest

from .helpers import make_player_session_context


@pytest.mark.parametrize(
    "field_name",
    ["firmware_revision", "hardware_revision", "protocol_version", "schema_version", "source"],
)
def test_rejects_empty_string_fields(field_name: str) -> None:
    with pytest.raises(ValueError):
        make_player_session_context(**{field_name: ""})


def test_permits_well_formed_context() -> None:
    context = make_player_session_context()
    assert context.player.player_id == "p1"
    assert context.session.session_id == "s1"
