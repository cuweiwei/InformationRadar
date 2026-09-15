import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from radar.lifecycle import ContextHubPublicationClient, HermesEventClient, InsightLifecycle, IntegrationError, hub_item_for
from radar.pipeline import RadarPipeline
from radar.provenance import insight_hash
from radar.server import RadarServer
from radar.storage import Storage
from radar.topics import TopicRegistry


class FakeHub:
    def __init__(self):
        self.published = []
        self.withdrawn = []

    def publish(self, insight, operation_key):
        self.published.append((insight["insight_id"], insight["revision"], operation_key))
        return {"status": "CANDIDATE", "hub_item_id": "hub-1", "hub_revision": insight["revision"], "receipt": {"provider": "contexthub", "publication_id": "pub-1"}}

    def withdraw(self, insight, operation_key):
        self.withdrawn.append((insight["insight_id"], operation_key))
        return {"status": "CONFIRMED", "receipt": {"provider": "contexthub", "withdrawal_id": "wd-1"}}


class FakeHermes:
    def __init__(self):
        self.events = []

    def deliver(self, event):
        self.events.append(event)
        return {"status": "ACCEPTED_BY_HERMES", "receipt": {"provider": "hermes", "receipt_id": "receipt-1", "accepted_at": "2026-09-15T00:00:00+00:00"}}


class ContractHandler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append({"method": "POST", "path": self.path, "headers": dict(self.headers), "body": body})
        if self.path == "/v1/radar/publications":
            if body.get("action") == "withdraw":
                payload = {"status": "withdrawn", "publication_id": "pub-http-withdraw", "hub_withdrawal_status": "applied"}
            else:
                payload = {"status": "candidate", "publication_id": "pub-http", "hub_item_id": "hub-http", "hub_revision": 1}
        elif self.path == "/api/internal/hermes/events":
            payload = {"event": {"event_id": body["event_id"]}, "replayed": False}
        else:
            self.send_error(404)
            return
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        self.__class__.requests.append({"method": "GET", "path": self.path, "headers": dict(self.headers), "body": {}})
        encoded = json.dumps({"publications": [{"insight_id": "insight-1", "insight_revision": 1, "action": "publish", "status": "accepted", "hub_item_id": "hub-http", "hub_item_revision": 2, "hub_withdrawal_status": "not_requested"}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def value(summary="A bounded summary", revision=None):
    result = {
        "insight_id": "insight-1",
        "topic_id": "ai_tools",
        "title": "A tool",
        "summary": summary,
        "sources": [{"source": "github", "source_item_id": "acme/tool", "url": "https://github.com/acme/tool", "published_at": "2026-09-15T00:00:00+00:00", "title": "acme/tool"}],
        "detected_at": "2026-09-15T00:00:00+00:00",
        "confidence_basis": {"source_count": 1},
        "confidence": 0.9,
        "importance": 0.8,
        "tags": ["rising"],
        "entities": ["acmetool"],
        "evidence": [{"kind": "source", "value": "github"}],
    }
    result["content_hash"] = insight_hash(result)
    if revision is not None:
        result["revision"] = revision
    return result


class V2LifecycleTests(unittest.TestCase):
    def test_insight_revisions_are_immutable_and_withdrawn_cannot_resurrect(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            lifecycle = InsightLifecycle(storage, FakeHub(), FakeHermes())
            first = lifecycle.record(value())
            replay = lifecycle.record(value())
            self.assertEqual(first["revision"], 1)
            self.assertEqual(replay["revision"], 1)
            second = lifecycle.record(value("A corrected bounded summary"))
            self.assertEqual(second["revision"], 2)
            self.assertEqual(storage.get_insight("insight-1", 1)["status"], "CORRECTED")
            self.assertEqual(storage.get_insight("insight-1", 2)["status"], "ACTIVE")
            with self.assertRaisesRegex(ValueError, "INSIGHT_REVISION_CONFLICT"):
                lifecycle.record(value("another", revision=1))
            lifecycle.withdraw("insight-1")
            self.assertEqual(storage.get_insight("insight-1")["status"], "WITHDRAWN")
            with self.assertRaisesRegex(ValueError, "INSIGHT_WITHDRAWN"):
                lifecycle.record(value("post-withdrawal"))
            storage.close()

    def test_publication_stays_candidate_and_event_is_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            hub = FakeHub()
            hermes = FakeHermes()
            lifecycle = InsightLifecycle(storage, hub, hermes)
            insight = lifecycle.record(value())
            publication = lifecycle.publish("insight-1", insight["revision"])
            self.assertEqual(publication["status"], "CANDIDATE")
            self.assertEqual(len(hub.published), 1)
            event = lifecycle.enqueue_event("insight-1", event_id="event-1", occurred_at="2026-09-15T00:01:00+00:00", sequence=1)
            replay = lifecycle.enqueue_event("insight-1", event_id="event-1", occurred_at="2026-09-15T00:01:00+00:00", sequence=1)
            self.assertEqual(event["event_id"], replay["event_id"])
            self.assertFalse(event["payload"].get("payload", {}).get("is_execution_authorization", True))
            delivered = lifecycle.deliver_event("event-1")
            self.assertEqual(delivered["outbox_state"], "ACCEPTED_BY_HERMES")
            self.assertEqual(delivered["receipt"]["receipt_id"], "receipt-1")
            self.assertEqual(storage.publication_for("insight-1", 1)["status"], "CANDIDATE")
            withdrawn = lifecycle.withdraw("insight-1")
            self.assertEqual(withdrawn["publication"]["status"], "CANDIDATE")
            self.assertEqual(withdrawn["withdrawal"]["status"], "WITHDRAWN")
            self.assertEqual(storage.publication_for("insight-1", 1, "publish")["status"], "CANDIDATE")
            self.assertEqual(storage.publication_for("insight-1", 1, "withdraw")["hub_withdrawal_status"], "CONFIRMED")
            storage.close()

    def test_withdrawal_tombstone_is_durable_and_blocks_late_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "radar.db")
            hub = FakeHub()
            storage = Storage(path)
            lifecycle = InsightLifecycle(storage, hub, FakeHermes())
            lifecycle.record(value())
            first = lifecycle.withdraw("insight-1")
            second = lifecycle.withdraw("insight-1")
            self.assertEqual(first["withdrawal"]["status"], "WITHDRAWN")
            self.assertEqual(first["withdrawal"]["publication_id"], second["withdrawal"]["publication_id"])
            self.assertEqual(first["event"]["event_id"], second["event"]["event_id"])
            self.assertIsNone(first["publication"])
            self.assertEqual(hub.withdrawn, [])
            with self.assertRaisesRegex(ValueError, "INSIGHT_WITHDRAWN"):
                lifecycle.publish("insight-1")
            storage.close()
            reopened = Storage(path)
            self.assertEqual(reopened.publication_for("insight-1", 1, "withdraw")["status"], "WITHDRAWN")
            reopened.close()

    def test_successful_withdrawal_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            hub = FakeHub()
            lifecycle = InsightLifecycle(storage, hub, FakeHermes())
            lifecycle.record(value())
            lifecycle.publish("insight-1")
            first = lifecycle.withdraw("insight-1")
            second = lifecycle.withdraw("insight-1")
            self.assertEqual(first["withdrawal"]["status"], "WITHDRAWN")
            self.assertEqual(second["withdrawal"]["status"], "WITHDRAWN")
            self.assertEqual(len(hub.withdrawn), 1)
            storage.close()

    def test_corrected_revision_cannot_publish_or_enqueue_new_event(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            lifecycle = InsightLifecycle(storage, FakeHub(), FakeHermes())
            lifecycle.record(value())
            lifecycle.record(value("Corrected summary"))
            with self.assertRaisesRegex(ValueError, "INSIGHT_REVISION_STALE"):
                lifecycle.publish("insight-1", 1)
            with self.assertRaisesRegex(ValueError, "INSIGHT_REVISION_STALE"):
                lifecycle.enqueue_event("insight-1", 1, event_id="late-old-event")
            storage.close()

    def test_event_expiry_and_unknown_delivery_are_not_blindly_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            lifecycle = InsightLifecycle(storage, FakeHub(), object())
            lifecycle.record(value())
            past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            lifecycle.enqueue_event("insight-1", event_id="expired", expires_at=past, occurred_at="2026-09-15T00:00:00+00:00", sequence=1)
            expired = lifecycle.deliver_event("expired")
            self.assertEqual(expired["outbox_state"], "EXPIRED")
            self.assertEqual(expired["receipt"]["disposition"], "ignored_expired")
            lifecycle.hermes = type("UnknownHermes", (), {"deliver": lambda self, event: {"status": "UNKNOWN", "error": "provider receipt unavailable"}})()
            lifecycle.enqueue_event("insight-1", event_id="unknown", occurred_at="2026-09-15T00:00:00+00:00", sequence=2)
            unknown = lifecycle.deliver_event("unknown")
            self.assertEqual(unknown["outbox_state"], "UNKNOWN")
            blocked = lifecycle.deliver_event("unknown")
            self.assertEqual(blocked["delivery_blocked"], "UNKNOWN_REQUIRES_RECONCILIATION")
            storage.close()

    def test_pending_and_unknown_delivery_recover_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "radar.db")
            storage = Storage(path)
            lifecycle = InsightLifecycle(storage, FakeHub(), FakeHermes())
            lifecycle.record(value())
            pending = lifecycle.enqueue_event("insight-1", event_id="restart-pending")
            first_sequence = pending["sequence"]
            storage.close()

            reopened = Storage(path)
            lifecycle = InsightLifecycle(reopened, FakeHub(), FakeHermes())
            delivered = lifecycle.deliver_event("restart-pending")
            self.assertEqual(delivered["outbox_state"], "ACCEPTED_BY_HERMES")
            next_event = lifecycle.enqueue_event("insight-1", event_id="restart-next")
            self.assertGreater(next_event["sequence"], first_sequence)
            reopened.update_event_delivery("restart-next", "SENDING")
            reopened.close()

            resumed = Storage(path)
            lifecycle = InsightLifecycle(resumed, FakeHub(), FakeHermes())
            blocked = lifecycle.deliver_event("restart-next")
            self.assertEqual(blocked["delivery_blocked"], "UNKNOWN_REQUIRES_RECONCILIATION")
            retried = lifecycle.deliver_event("restart-next", allow_unknown_retry=True)
            self.assertEqual(retried["outbox_state"], "ACCEPTED_BY_HERMES")
            resumed.close()

    def test_old_queued_event_is_suppressed_after_new_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            hermes = FakeHermes()
            lifecycle = InsightLifecycle(storage, FakeHub(), hermes)
            lifecycle.record(value())
            old_event = lifecycle.enqueue_event("insight-1", event_id="old-event", sequence=1)
            lifecycle.record(value("New revision"))
            new_event = lifecycle.enqueue_event("insight-1", event_id="new-event", sequence=2)
            stale = lifecycle.deliver_event(old_event["event_id"])
            fresh = lifecycle.deliver_event(new_event["event_id"])
            self.assertEqual(stale["outbox_state"], "STALE")
            self.assertEqual(stale["receipt"]["disposition"], "suppressed_stale_revision")
            self.assertEqual(fresh["outbox_state"], "ACCEPTED_BY_HERMES")
            self.assertEqual([event["subject_revision"] for event in hermes.events], [2])
            storage.close()

    def test_event_delivery_requires_a_durable_hermes_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            lifecycle = InsightLifecycle(storage, FakeHub(), type("NoReceiptHermes", (), {"deliver": lambda self, event: {"status": "ACCEPTED_BY_HERMES"}})())
            lifecycle.record(value())
            lifecycle.enqueue_event("insight-1", event_id="no-receipt")
            result = lifecycle.deliver_event("no-receipt")
            self.assertEqual(result["outbox_state"], "UNKNOWN")
            self.assertEqual(result["last_error"], "PROVIDER_RECEIPT_MISSING")
            storage.close()

    def test_event_id_conflict_is_not_hidden_by_replay_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            lifecycle = InsightLifecycle(storage, FakeHub(), FakeHermes())
            lifecycle.record(value())
            lifecycle.enqueue_event("insight-1", event_id="same-event", summary="first")
            with self.assertRaisesRegex(ValueError, "EVENT_ID_CONFLICT"):
                lifecycle.enqueue_event("insight-1", event_id="same-event", summary="different")
            storage.close()

    def test_hub_payload_is_bounded_and_has_separate_hash(self):
        item = hub_item_for(value())
        self.assertEqual(item["type"], "insight")
        self.assertEqual(len(item["content_hash"]), 64)
        self.assertEqual(item["source_item_id"], "radar:insight-1:r1")
        self.assertNotIn("body", item)

    def test_http_adapters_send_the_cross_system_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            lifecycle = InsightLifecycle(storage, FakeHub(), FakeHermes())
            insight = lifecycle.record(value())
            ContractHandler.requests = []
            server = ThreadingHTTPServer(("127.0.0.1", 0), ContractHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = "http://127.0.0.1:%d" % server.server_port
            try:
                hub = ContextHubPublicationClient(base_url, "hub-token")
                hub_result = hub.publish(insight, "radar:publish:insight-1:r1")
                event = lifecycle.enqueue_event("insight-1", event_id="event-http", sequence=1)
                hermes = HermesEventClient(base_url, "event-token", path="/api/internal/hermes/events")
                event_result = hermes.deliver(event)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                storage.close()
            self.assertEqual(hub_result["status"], "CANDIDATE")
            self.assertEqual(event_result["status"], "ACCEPTED_BY_HERMES")
            hub_request, hermes_request = ContractHandler.requests
            self.assertEqual(hub_request["path"], "/v1/radar/publications")
            self.assertEqual(hub_request["headers"]["Authorization"], "Bearer hub-token")
            self.assertEqual(hub_request["headers"].get("Idempotency-Key") or hub_request["headers"].get("Idempotency-key"), "radar:publish:insight-1:r1")
            self.assertEqual(hub_request["body"]["content_hash"], insight["content_hash"])
            self.assertEqual(hub_request["body"]["hub_content_hash"], hub_item_for(insight)["content_hash"])
            self.assertNotIn("content_hash", hub_request["body"]["item"])
            self.assertNotIn("source_item_id", hub_request["body"]["item"])
            self.assertEqual(hermes_request["path"], "/api/internal/hermes/events")
            self.assertEqual(hermes_request["headers"]["Authorization"], "Bearer event-token")
            self.assertEqual(hermes_request["headers"].get("Idempotency-Key") or hermes_request["headers"].get("Idempotency-key"), "event-http")
            self.assertEqual(set(hermes_request["body"]), {"source", "event_id", "payload"})
            self.assertEqual(hermes_request["body"]["source"], "information-radar")

    def test_http_hub_withdraw_and_reconcile_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            ContractHandler.requests = []
            server = ThreadingHTTPServer(("127.0.0.1", 0), ContractHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = "http://127.0.0.1:%d" % server.server_port
            try:
                hub = ContextHubPublicationClient(base_url, "hub-token")
                withdrawn = hub.withdraw(value(revision=1), "radar:withdraw:insight-1:r1")
                reconciliation = hub.reconcile("insight-1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                storage.close()
            self.assertEqual(withdrawn["status"], "CONFIRMED")
            self.assertEqual(reconciliation["publications"][0]["status"], "accepted")
            withdraw_request, reconcile_request = ContractHandler.requests[-2:]
            self.assertEqual(withdraw_request["body"]["action"], "withdraw")
            self.assertNotIn("item", withdraw_request["body"])
            self.assertNotIn("hub_content_hash", withdraw_request["body"])
            self.assertEqual(reconcile_request["path"], "/v1/radar/publications?insight_id=insight-1&limit=100")

    def test_unknown_publication_reconciles_after_restart(self):
        class UnknownHub:
            def publish(self, insight, operation_key):
                raise IntegrationError("DELIVERY_UNKNOWN", "receipt unavailable", unknown=True)

            def reconcile(self, insight_id):
                return {"publications": [{"insight_id": insight_id, "insight_revision": 1, "action": "publish", "status": "accepted", "hub_item_id": "hub-reconciled", "hub_item_revision": 2, "hub_withdrawal_status": "not_requested"}]}

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "radar.db")
            storage = Storage(path)
            lifecycle = InsightLifecycle(storage, UnknownHub(), FakeHermes())
            lifecycle.record(value())
            unknown = lifecycle.publish("insight-1")
            self.assertEqual(unknown["status"], "UNKNOWN")
            storage.close()
            reopened = Storage(path)
            lifecycle = InsightLifecycle(reopened, UnknownHub(), FakeHermes())
            reconciled = lifecycle.reconcile_publication("insight-1")
            self.assertEqual(reconciled["publications"][0]["status"], "accepted".upper())
            self.assertEqual(reconciled["publications"][0]["hub_item_id"], "hub-reconciled")
            reopened.close()

    def test_unknown_publication_requires_reconciliation_before_retry(self):
        class UnknownHub:
            def __init__(self):
                self.calls = 0

            def publish(self, insight, operation_key):
                self.calls += 1
                raise IntegrationError("DELIVERY_UNKNOWN", "receipt unavailable", unknown=True)

            def reconcile(self, insight_id):
                return {"publications": []}

        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            hub = UnknownHub()
            lifecycle = InsightLifecycle(storage, hub, FakeHermes())
            lifecycle.record(value())
            unknown = lifecycle.publish("insight-1")
            blocked = lifecycle.publish("insight-1")
            self.assertEqual(unknown["status"], "UNKNOWN")
            self.assertEqual(blocked["publication_blocked"], "UNKNOWN_REQUIRES_RECONCILIATION")
            self.assertEqual(hub.calls, 1)
            storage.close()

    def test_projection_is_bearer_protected_and_contains_only_summary_state(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(os.path.join(directory, "radar.db"))
            pipeline = RadarPipeline(storage, TopicRegistry.default())
            pipeline.lifecycle = InsightLifecycle(storage, FakeHub(), FakeHermes())
            pipeline.lifecycle.record(value())
            app = RadarServer("src/web", storage, TopicRegistry.default(), pipeline)
            server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = "http://127.0.0.1:%d/api/v2/radar/projection" % server.server_port
            try:
                with self.assertRaises(HTTPError) as missing:
                    urlopen(url)
                self.assertEqual(missing.exception.code, 503)
                with patch.dict(os.environ, {"RADAR_PROJECTION_TOKEN": "projection-secret"}, clear=False):
                    with self.assertRaises(HTTPError) as denied:
                        urlopen(Request(url, headers={"Authorization": "Bearer wrong"}))
                    self.assertEqual(denied.exception.code, 401)
                    response = urlopen(Request(url, headers={"Authorization": "Bearer projection-secret"}))
                    payload = json.load(response)
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["source_id"], "information-radar")
                self.assertEqual(payload["data"]["insights"][0]["insight_id"], "insight-1")
                self.assertEqual(payload["data"]["raw_data"], "radar_owned_not_projected")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                storage.close()


if __name__ == "__main__":
    unittest.main()
