import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .demo import demo_signals
from .pipeline import RadarPipeline
from .settings import SETTING_DEFINITIONS, status_payload
from .storage import Storage
from .topics import TopicRegistry


def _json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
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
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
                return app.static(self, parsed.path)

            def do_POST(self):
                parsed = urlparse(self.path)
                if parsed.path not in ("/api/run", "/api/settings", "/api/verify"):
                    return _json_response(self, 404, {"error": "not found"})
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length) if length else b"{}"
                payload = json.loads(body.decode("utf-8"))
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
