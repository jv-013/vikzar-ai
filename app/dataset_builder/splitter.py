"""Deterministic group-level splitting for leakage-safe training datasets."""

from __future__ import annotations

import hashlib
import math

from .contracts import DatasetSplit, DatasetSplitPolicy


class GroupedDatasetSplitter:
    """Assign connected player/session evidence components to one split."""

    def assign(
        self,
        groups: set[tuple[str, str]],
        policy: DatasetSplitPolicy,
    ) -> dict[tuple[str, str], DatasetSplit]:
        """Return stable assignments without player or session leakage.

        A component contains every player/session pair connected through a
        shared player or a shared session. Assigning entire components prevents
        both one player's history and a collective session from crossing split
        boundaries.
        """

        if not groups:
            return {}
        components = self._components(groups)
        ordered_components = sorted(
            components,
            key=lambda component: hashlib.sha256(
                f"{policy.seed}\x00{self._component_key(component)}".encode("utf-8")
            ).hexdigest(),
        )
        splits = (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST)
        fractions = (policy.train_fraction, policy.validation_fraction, policy.test_fraction)
        counts = self._allocate_counts(len(ordered_components), fractions)

        assignment: dict[tuple[str, str], DatasetSplit] = {}
        offset = 0
        for split, count in zip(splits, counts):
            for component in ordered_components[offset : offset + count]:
                for group in component:
                    assignment[group] = split
            offset += count
        return assignment

    @staticmethod
    def _components(groups: set[tuple[str, str]]) -> tuple[frozenset[tuple[str, str]], ...]:
        """Find transitive components sharing a player or a session identifier."""

        by_player: dict[str, set[tuple[str, str]]] = {}
        by_session: dict[str, set[tuple[str, str]]] = {}
        for group in groups:
            by_player.setdefault(group[0], set()).add(group)
            by_session.setdefault(group[1], set()).add(group)

        remaining = set(groups)
        components: list[frozenset[tuple[str, str]]] = []
        while remaining:
            pending = [next(iter(remaining))]
            component: set[tuple[str, str]] = set()
            while pending:
                group = pending.pop()
                if group in component:
                    continue
                component.add(group)
                remaining.discard(group)
                pending.extend(by_player[group[0]] - component)
                pending.extend(by_session[group[1]] - component)
            components.append(frozenset(component))
        return tuple(components)

    @staticmethod
    def _component_key(component: frozenset[tuple[str, str]]) -> str:
        """Return an unambiguous deterministic component identity for hashing."""

        return "\x1e".join(f"{player_id}\x00{session_id}" for player_id, session_id in sorted(component))

    @staticmethod
    def _allocate_counts(total: int, fractions: tuple[float, float, float]) -> tuple[int, int, int]:
        """Allocate exact group counts using deterministic largest remainders."""

        raw = [total * fraction for fraction in fractions]
        counts = [math.floor(value) for value in raw]
        remaining = total - sum(counts)
        for index in sorted(range(len(raw)), key=lambda item: (-(raw[item] - counts[item]), item))[:remaining]:
            counts[index] += 1
        return tuple(counts)  # type: ignore[return-value]
