import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from radar.collectors.base import Collector
from radar.entity_resolution import resolve_signal
from radar.models import CollectorResult, RawSignal
from radar.pipeline import RadarPipeline
from radar.scoring import acceleration, early_signal_score, lifecycle, velocity
from radar.server import RadarServer
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

    def test_storage_health_backup_and_delivery_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "source.db")
            backup = os.path.join(directory, "backup.db")
            storage = Storage(source)
            self.assertTrue(storage.health()["schema_ready"])
            storage.set_setting("GITHUB_TOKEN", "token")
            storage.backup_to(backup)
            restored = Storage(backup)
            self.assertEqual(restored.get_setting("GITHUB_TOKEN"), "token")
            restored.close()
            storage.close()

    def test_operations_health_reports_release_and_unverified_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "ops.db"))
            app = RadarServer("src/web", storage, TopicRegistry.default(), None)
            commit = "a" * 40
            digest = "sha256:" + "b" * 64
            with patch.dict(os.environ, {"AIHP_RELEASE_COMMIT": commit, "AIHP_IMAGE_DIGEST": digest}):
                payload = app.operations_health()
            self.assertEqual(payload["service"], "information-radar")
            self.assertEqual(payload["release"], {"commit": commit, "imageDigest": digest})
            self.assertEqual(payload["database"], {"status": "ok", "schemaReady": True, "readiness": "ready"})
            self.assertFalse(payload["backup"]["adapterVerified"])
            self.assertFalse(payload["restoreTest"]["adapterVerified"])
            self.assertFalse(payload["secretAdapter"]["adapterVerified"])
            storage.close()

    def test_operations_health_does_not_expose_invalid_release_values(self):
        storage = Storage(":memory:")
        app = RadarServer("src/web", storage, TopicRegistry.default(), None)
        with patch.dict(os.environ, {"AIHP_RELEASE_COMMIT": "secret", "AIHP_IMAGE_DIGEST": "latest"}):
            self.assertEqual(app.operations_health()["release"], {"commit": None, "imageDigest": None})
        storage.close()

    def test_operations_health_get_endpoint(self):
        storage = Storage(":memory:")
        app = RadarServer("src/web", storage, TopicRegistry.default(), None)
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = "http://127.0.0.1:%d/health/ops" % server.server_port
            with urlopen(url) as response:
                payload = json.load(response)
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["service"], "information-radar")
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url, data=b"{}", method="POST"))
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            storage.close()

    def test_release_manifest_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            compose = os.path.join(directory, "compose.prod.yml")
            output = os.path.join(directory, "release-manifest.json")
            with open(compose, "wb") as file_handle:
                file_handle.write(b"services: {}\n")
            commit = "c" * 40
            digest = "sha256:" + "d" * 64
            subprocess.run(
                [sys.executable, "scripts/generate-release-manifest.py", "--commit", commit, "--image-digest", digest, "--compose", compose, "--output", output],
                check=True,
            )
            with open(output, encoding="utf-8") as file_handle:
                manifest = json.load(file_handle)
            self.assertEqual(manifest["schemaVersion"], 1)
            self.assertEqual(manifest["serviceId"], "information-radar")
            self.assertEqual(manifest["repository"], "cuweiwei/InformationRadar")
            self.assertEqual(manifest["commitSha"], commit)
            self.assertEqual(manifest["imageDigest"], digest)
            self.assertEqual(manifest["composePath"], "compose.prod.yml")
            self.assertEqual(manifest["composeSha256"], "fa6ccea1ca4e3a031d9e99f25cc05db803aa9bac642c000ddab14f6d9da54b52")
            self.assertEqual(manifest["deploymentProjectId"], "information-radar")
            self.assertEqual(manifest["health"], {"path": "/health", "readinessPath": "/health/ready"})


if __name__ == "__main__":
    unittest.main()
