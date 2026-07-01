"""Tests for provider health tracking."""

import time

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.provider_health import (
    ProviderHealthTracker,
)


def test_record_success():
    tracker = ProviderHealthTracker()
    tracker.record("crossref", success=True, latency_ms=200)
    stats = tracker.get_stats("crossref")
    assert stats.success_count == 1
    assert stats.failure_count == 0
    assert stats.avg_latency_ms == 200.0


def test_record_failure():
    tracker = ProviderHealthTracker()
    tracker.record("crossref", success=False, latency_ms=5000)
    stats = tracker.get_stats("crossref")
    assert stats.success_count == 0
    assert stats.failure_count == 1


def test_success_rate():
    tracker = ProviderHealthTracker()
    for _ in range(7):
        tracker.record("crossref", success=True, latency_ms=100)
    for _ in range(3):
        tracker.record("crossref", success=False, latency_ms=5000)
    stats = tracker.get_stats("crossref")
    assert stats.success_rate == 0.7


def test_deprioritize_unhealthy():
    tracker = ProviderHealthTracker()
    # 80% failure rate
    for _ in range(2):
        tracker.record("bad_provider", success=True, latency_ms=100)
    for _ in range(8):
        tracker.record("bad_provider", success=False, latency_ms=5000)
    # Healthy provider
    for _ in range(10):
        tracker.record("good_provider", success=True, latency_ms=100)

    plan = [
        {"route": "api", "provider": "bad_provider"},
        {"route": "api", "provider": "good_provider"},
    ]
    reordered = tracker.reorder_plan(plan)
    assert reordered[0]["provider"] == "good_provider"


def test_unknown_provider_neutral():
    tracker = ProviderHealthTracker()
    stats = tracker.get_stats("unknown")
    assert stats.success_rate == 1.0  # assume healthy


def test_window_expiry():
    tracker = ProviderHealthTracker(window_seconds=1)
    tracker.record("p1", success=True, latency_ms=100)
    time.sleep(1.1)
    stats = tracker.get_stats("p1")
    assert stats.success_count == 0  # expired
