"""Lookup engine implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .matchers import Matcher
from .enrichers import Enricher
from .encoders import Encoder


class LookupEngine:
    def __init__(self, data_source: Dict[str, Any]):
        self.data_source = data_source
        self.matchers: Dict[str, Matcher] = {}
        self.enrichers: Dict[str, Enricher] = {}
        self.encoders: Dict[str, Encoder] = {}

    def register_matcher(self, name: str, matcher: Matcher) -> None:
        self.matchers[name] = matcher

    def register_enricher(self, name: str, enricher: Enricher) -> None:
        self.enrichers[name] = enricher

    def register_encoder(self, name: str, encoder: Encoder) -> None:
        self.encoders[name] = encoder

    def find(self, query: str, matcher_name: str) -> Any:
        matcher = self.matchers.get(matcher_name)
        if matcher is None:
            raise KeyError(f"Matcher {matcher_name} not found")
        return matcher.match(query, self.data_source)

    def enrich(self, item: Any, enricher_name: str) -> Any:
        enricher = self.enrichers.get(enricher_name)
        if enricher is None:
            raise KeyError(f"Enricher {enricher_name} not found")
        return enricher.enrich(item)

    def encode(self, item: Any, encoder_name: str) -> Any:
        encoder = self.encoders.get(encoder_name)
        if encoder is None:
            raise KeyError(f"Encoder {encoder_name} not found")
        return encoder.encode(item)
