"""Thread-safe process-local observability metrics."""

from __future__ import annotations

from threading import RLock

from .contracts import MetricsSnapshot


class MetricsRegistry:
    """Record counters without changing scientific outputs."""

    def __init__(self) -> None:
        self._requests_total = 0
        self._requests_failed = 0
        self._pipeline_requests = 0
        self._pipeline_failures = 0
        self._pipeline_latency_ms_total = 0.0
        self._lock = RLock()

    def record_request(self, *, failed: bool) -> None:
        with self._lock:
            self._requests_total += 1
            self._requests_failed += int(failed)

    def record_pipeline(self, *, latency_ms: float, failed: bool) -> None:
        with self._lock:
            self._pipeline_requests += 1
            self._pipeline_failures += int(failed)
            self._pipeline_latency_ms_total += latency_ms

    def snapshot(
        self,
        *,
        firebase_queued_operations: int,
        active_sessions: int,
    ) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(
                requests_total=self._requests_total,
                requests_failed=self._requests_failed,
                pipeline_requests=self._pipeline_requests,
                pipeline_failures=self._pipeline_failures,
                pipeline_latency_ms_total=self._pipeline_latency_ms_total,
                firebase_queued_operations=firebase_queued_operations,
                active_sessions=active_sessions,
            )
