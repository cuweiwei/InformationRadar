import json
import hmac
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .demo import demo_signals
from .pipeline import RadarPipeline
from .settings import SETTING_DEFINITIONS, effective_settings, status_payload
from .storage import Storage
from .topics import TopicRegistry


COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
IMAGE_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$", re.IGNORECASE)


def _json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class RadarServer:
    def __init__(self, root, storage, registry, pipeline):
        self.root = os.path.abspath(root)
        self.storage = storage
        self.registry = registry
        self.pipeline = pipeline

    def handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Idempotency-Key")
                self.end_headers()

            def do_GET(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                topic_id = query.get("topic", ["ai_tools"])[0]
                if parsed.path == "/health":
                    return _json_response(self, 200, {"status": "ok", **app.storage.health()})
                if parsed.path == "/health/ready":
                    health = app.storage.health()
                    status = 200 if health["schema_ready"] else 503
                    return _json_response(self, status, {"status": "ready" if status == 200 else "not_ready", **health})
                if parsed.path == "/health/ops":
                    return _json_response(self, 200, app.operations_health())
                if parsed.path == "/api/topics":
                    return _json_response(self, 200, {"topics": [{"id": item.config.id, "name": item.config.name, "description": item.config.description} for item in app.registry.all() if item.config.id != "test_topic"]})
                if parsed.path == "/api/state":
                    return _json_response(self, 200, app.state(topic_id))
                if parsed.path == "/api/digest":
                    return _json_response(self, 200, app.storage.latest_digest(topic_id) or {"topic": topic_id, "text": "", "payload": {}})
                if parsed.path == "/api/health":
                    return _json_response(self, 200, {"topic": topic_id, "runs": app.storage.latest_runs(topic_id), "delivery": app.storage.latest_delivery(topic_id)})
                if parsed.path == "/api/settings":
                    return _json_response(self, 200, {"settings": status_payload(app.storage)})
                if parsed.path == "/api/v2/insights":
                    return _json_response(self, 200, {"source_id": "information-radar", "insights": app.pipeline.lifecycle.projection(topic_id if "topic" in query else None)["data"]["insights"]})
                if parsed.path.startswith("/api/v2/insights/"):
                    insight_id = parsed.path.split("/", 4)[4]
                    insight = app.storage.get_insight(insight_id)
                    if insight:
                        return _json_response(self, 200, {"insight": insight, "publication": app.storage.publication_for(insight_id, insight["revision"], "publish"), "withdrawal": app.storage.latest_publication(insight_id, "withdraw")})
                    return _json_response(self, 404, {"error": {"code": "not_found", "message": "insight not found"}})
                if parsed.path == "/api/v2/radar/projection" or parsed.path == "/api/v2/projection":
                    return app.projection_response(self)
                if parsed.path.startswith("/api/v2/events/"):
                    event_id = parsed.path.split("/", 4)[4]
                    event = app.storage.event(event_id)
                    return _json_response(self, 200, {"event": event}) if event else _json_response(self, 404, {"error": {"code": "not_found", "message": "event not found"}})
                return app.static(self, parsed.path)

            def do_POST(self):
                parsed = urlparse(self.path)
                if parsed.path not in ("/api/run", "/api/settings", "/api/verify") and not parsed.path.startswith("/api/v2/"):
                    return _json_response(self, 404, {"error": "not found"})
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    return _json_response(self, 400, {"error": {"code": "invalid_request", "message": "request body must be JSON"}})
                if parsed.path.startswith("/api/v2/"):
                    if not isinstance(payload, dict):
                        return _json_response(self, 400, {"error": {"code": "invalid_request", "message": "request body must be an object"}})
                    app.pipeline.configure_integrations()
                if parsed.path == "/api/v2/insights":
                    if not isinstance(payload, dict) or not payload.get("topic_id") or not payload.get("title") or not payload.get("summary"):
                        return _json_response(self, 400, {"error": {"code": "invalid_request", "message": "topic_id, title and summary are required"}})
                    try:
                        insight = app.pipeline.lifecycle.record({key: value for key, value in payload.items() if key not in ("status", "content_hash", "revision")})
                        return _json_response(self, 201, {"insight": app.storage.get_insight(insight["insight_id"], insight["revision"]), "created": True})
                    except (ValueError, KeyError) as error:
                        return _json_response(self, 409, {"error": {"code": str(error), "message": str(error)}})
                if parsed.path.startswith("/api/v2/insights/"):
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) != 5 or parts[0:3] != ["api", "v2", "insights"]:
                        return _json_response(self, 404, {"error": {"code": "not_found", "message": "not found"}})
                    insight_id, operation = parts[3], parts[4]
                    try:
                        if operation == "publish":
                            result = app.pipeline.lifecycle.publish(insight_id, payload.get("revision"), payload.get("operation_key") or self.headers.get("Idempotency-Key", ""))
                        elif operation == "withdraw":
                            result = app.pipeline.lifecycle.withdraw(insight_id, payload.get("operation_key") or self.headers.get("Idempotency-Key", ""))
                        else:
                            return _json_response(self, 404, {"error": {"code": "not_found", "message": "not found"}})
                        return _json_response(self, 200, result)
                    except KeyError as error:
                        return _json_response(self, 404, {"error": {"code": str(error), "message": str(error)}})
                    except (ValueError, RuntimeError) as error:
                        return _json_response(self, 409, {"error": {"code": str(error), "message": str(error)}})
                if parsed.path == "/api/v2/events":
                    if not isinstance(payload, dict) or not payload.get("insight_id"):
                        return _json_response(self, 400, {"error": {"code": "invalid_request", "message": "insight_id is required"}})
                    try:
                        event = app.pipeline.lifecycle.enqueue_event(payload["insight_id"], payload.get("revision"), payload.get("event_type", "radar.actionable.v1"), payload.get("summary", ""), payload.get("priority", "normal"), bool(payload.get("action_required", True)), payload.get("expires_at"), payload.get("event_id") or self.headers.get("Idempotency-Key", ""), payload.get("sequence"), payload.get("occurred_at"))
                        return _json_response(self, 201, {"event": event})
                    except (KeyError, ValueError) as error:
                        return _json_response(self, 409, {"error": {"code": str(error), "message": str(error)}})
                if parsed.path.startswith("/api/v2/events/"):
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) != 5 or parts[0:3] != ["api", "v2", "events"] or parts[4] != "deliver":
                        return _json_response(self, 404, {"error": {"code": "not_found", "message": "not found"}})
                    try:
                        return _json_response(self, 200, app.pipeline.lifecycle.deliver_event(parts[3], bool(payload.get("allow_unknown_retry", False))))
                    except KeyError as error:
                        return _json_response(self, 404, {"error": {"code": str(error), "message": str(error)}})
                if parsed.path == "/api/settings":
                    changed = []
                    for key, value in payload.items():
                        if key not in SETTING_DEFINITIONS or not isinstance(value, str):
                            continue
                        definition = SETTING_DEFINITIONS[key]
                        # Blank secrets mean "keep the existing value"; non-secret values can be cleared.
                        if definition["secret"] and value == "":
                            continue
                        app.storage.set_setting(key, value, definition["secret"])
                        changed.append(key)
                    return _json_response(self, 200, {"saved": changed, "settings": status_payload(app.storage)})
                if parsed.path == "/api/verify":
                    target = payload.get("target", "")
                    delivery_test = bool(payload.get("delivery_test", False))
                    return _json_response(self, 200, app.pipeline.verify_connection(target, delivery_test))
                topic_id = payload.get("topic", "ai_tools")
                return _json_response(self, 200, app.pipeline.run(topic_id, deliver=bool(payload.get("deliver"))))

        return Handler

    def projection_response(self, handler):
        settings = effective_settings(self.storage)
        expected = settings.get("RADAR_PROJECTION_TOKEN", "")
        if not expected:
            return _json_response(handler, 503, {"error": {"code": "PROJECTION_AUTH_UNAVAILABLE", "message": "projection token is not configured"}})
        provided = handler.headers.get("Authorization", "")
        token = provided[7:].strip() if provided.startswith("Bearer ") else ""
        if not token or not hmac.compare_digest(token, expected):
            return _json_response(handler, 401, {"error": {"code": "UNAUTHORIZED", "message": "valid projection bearer token required"}})
        return _json_response(handler, 200, self.pipeline.lifecycle.projection())

    def operations_health(self):
        health = self.storage.health()
        schema_ready = bool(health["schema_ready"])
        commit = os.environ.get("AIHP_RELEASE_COMMIT", "")
        image_digest = os.environ.get("AIHP_IMAGE_DIGEST", "")
        return {
            "service": "information-radar",
            "release": {
                "commit": commit if COMMIT_SHA_PATTERN.fullmatch(commit) else None,
                "imageDigest": image_digest if IMAGE_DIGEST_PATTERN.fullmatch(image_digest) else None,
            },
            "database": {
                "status": health["database"],
                "schemaReady": schema_ready,
                "readiness": "ready" if schema_ready else "not_ready",
            },
            "backup": {
                "status": "local_only",
                "adapterVerified": False,
                "mechanism": "sqlite_online_backup",
            },
            "restoreTest": {
                "status": "manual_only",
                "adapterVerified": False,
            },
            "secretAdapter": {
                "status": "not_implemented",
                "adapterVerified": False,
                "credentialSource": "environment_or_local_settings",
            },
        }

    def state(self, topic_id):
        plugin = self.registry.get(topic_id)
        entities = self.pipeline.score_topic(plugin)
        runs = self.storage.latest_runs(topic_id, 10)
        digest = self.storage.latest_digest(topic_id)
        return {
            "topic": {"id": plugin.config.id, "name": plugin.config.name, "description": plugin.config.description},
            "entities": [entity.as_dict() for entity in entities],
            "stats": {"rising": sum(entity.status == "RISING" for entity in entities), "new": sum(entity.status == "NEW" for entity in entities), "watchlist": sum(entity.status in ("WATCHLIST", "COOLING") for entity in entities), "all": len(entities)},
            "runs": runs,
            "digest": digest,
        }

    def static(self, handler, requested_path):
        relative = requested_path.lstrip("/") or "index.html"
        full_path = os.path.abspath(os.path.join(self.root, relative))
        if not full_path.startswith(self.root) or not os.path.isfile(full_path):
            return _json_response(handler, 404, {"error": "not found"})
        content_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
        with open(full_path, "rb") as file_handle:
            body = file_handle.read()
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)


def serve(root, storage_path="data/radar.db", host="127.0.0.1", port=4173, seed_demo=True):
    storage = Storage(storage_path)
    registry = TopicRegistry.default()
    pipeline = RadarPipeline(storage, registry)
    if seed_demo and not storage.all_entities_for_topic("ai_tools"):
        pipeline.ingest_signals(registry.get("ai_tools"), demo_signals("ai_tools"))
    if seed_demo and not storage.all_entities_for_topic("housing"):
        pipeline.ingest_signals(registry.get("housing"), demo_signals("housing"))
    server = ThreadingHTTPServer((host, port), RadarServer(root, storage, registry, pipeline).handler())
    print("Information Radar listening on http://%s:%d" % (host, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        storage.close()
