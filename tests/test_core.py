import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from radar.collectors.base import Collector
from radar.entity_resolution import resolve_signal
from radar.models import CollectorResult, RawSignal
from radar.pipeline import RadarPipeline
from radar.scoring import acceleration, early_signal_score, lifecycle, velocity
from radar.storage import Storage
from radar.settings import effective_settings, status_payload
from radar.topics import TopicRegistry


class FakeCollector(Collector):
    source = "fixture"

    def __init__(self, signals):
        self.signals = signals

    def discover(self, topic, since):
        return CollectorResult(self.source, "SUCCESS", self.signals, items_fetched=len(self.signals), items_accepted=len(self.signals))


class CoreTests(unittest.TestCase):
    def test_fast_small_project_beats_popular_stable_project(self):
        fast = early_signal_score(90, 92, 50, 100, 92, 90, 0)["score"]
        stable = early_signal_score(20, 50, 20, 10, 92, 90, 20)["score"]
        self.assertGreater(fast, stable)

    def test_velocity_and_acceleration(self):
        now = datetime.now(timezone.utc)
        history = [(950, now), (450, now - timedelta(days=1)), (200, now - timedelta(days=2))]
        self.assertAlmostEqual(velocity(history), 500 / 24, places=3)
        self.assertGreater(acceleration(history), 1.0)

    def test_lifecycle_prefers_new_and_rising_states(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(lifecycle(90, now - timedelta(hours=2), 4, {"emerging": 45, "rising": 65, "trending": 80}, now), "NEW")
        self.assertEqual(lifecycle(72, now - timedelta(days=3), 2, {"emerging": 45, "rising": 65, "trending": 80}, now), "RISING")

    def test_entity_resolution_uses_github_repository(self):
        signal = RawSignal("github", "acme/tool", "https://github.com/acme/tool", "acme/tool", "agent tool")
        entity_id, confidence = resolve_signal(signal, [{"id": "entity-1", "canonical_name": "acmetool", "github_repo": "acme/tool", "official_domain": ""}])
        self.assertEqual(entity_id, "entity-1")
        self.assertEqual(confidence, 0.95)

    def test_generic_source_domain_does_not_merge_different_repositories(self):
        signal = RawSignal("github", "acme/other", "https://github.com/acme/other", "acme/other", "agent tool")
        entity_id, confidence = resolve_signal(signal, [{"id": "entity-1", "canonical_name": "acmetool", "github_repo": "acme/tool", "official_domain": "github.com"}])
        self.assertEqual(entity_id, "")
        self.assertEqual(confidence, 0.0)

    def test_topic_extensibility_and_pipeline(self):
        registry = TopicRegistry.default()
        self.assertEqual(registry.get("housing").config.name, "Housing")
        now = datetime.now(timezone.utc)
        signals = [
            RawSignal("fixture", "one", "https://example.com/one", "Signal project one", "agent project", published_at=now - timedelta(days=1), collected_at=now - timedelta(days=1), engagement={"score": 30}),
            RawSignal("fixture", "two", "https://example.com/two", "Signal project two", "agent project", published_at=now, collected_at=now, engagement={"score": 90}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "test.db"))
            pipeline = RadarPipeline(storage, registry, [FakeCollector(signals)])
            result = pipeline.run("test_topic", since=now - timedelta(days=2), dry_run=False)
            self.assertEqual(result["collectors"][0]["status"], "SUCCESS")
            self.assertGreaterEqual(result["entities"], 1)
            self.assertTrue(result["digest"])
            storage.close()

    def test_web_settings_are_redacted_and_used_by_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "settings.db"))
            storage.set_setting("GITHUB_TOKEN", "ghp_super_secret_value")
            statuses = {item["key"]: item for item in status_payload(storage)}
            self.assertTrue(statuses["GITHUB_TOKEN"]["configured"])
            self.assertNotIn("super_secret", statuses["GITHUB_TOKEN"]["masked"])
            self.assertEqual(effective_settings(storage)["GITHUB_TOKEN"], "ghp_super_secret_value")
            storage.close()


if __name__ == "__main__":
    unittest.main()
