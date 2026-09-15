"""Radar v2 insight, publication, event and projection lifecycle.

The service deliberately has no Worker or Hermes planning authority.  It
stores Radar-owned evidence, submits ContextHub candidates, and emits
actionable events with bounded summaries.  Every downstream acknowledgement
is recorded independently from the source insight.
"""

import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .provenance import event_hash, hub_content_hash, insight_hash, publication_hash, sha256_json
from .storage import Storage, isoformat, parse_time


SOURCE_ID = "information-radar"


class IntegrationError(RuntimeError):
    def __init__(self, code: str, message: str, unknown: bool = False):
        super().__init__(message)
        self.code = code
        self.unknown = unknown


def _now() -> str:
    return isoformat(datetime.now(timezone.utc)) or ""


def _bounded_text(value: Any, limit: int = 2000) -> str:
    return str(value or "")[:limit]


def _is_expired(value: Optional[str]) -> bool:
    if not value:
        return False
    try:
        return parse_time(value) <= datetime.now(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return False


def _receipt_summary(receipt: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(receipt, dict):
        return None
    return {key: receipt[key] for key in ("provider", "receipt_id", "destination_ref", "accepted_at", "replayed", "publication_id", "withdrawal_id") if key in receipt}


def hub_item_for(insight: Dict[str, Any], source_uri: str = "") -> Dict[str, Any]:
    """Build the canonical ContextHub NewItem-shaped candidate payload."""
    tags = [str(value).strip() for value in insight.get("tags", []) if str(value).strip()]
    entities = [str(value).strip() for value in insight.get("entities", []) if str(value).strip()]
    data = {
        "source": SOURCE_ID,
        "insight_id": insight["insight_id"],
        "revision": int(insight.get("revision") or 1),
        "content_hash": insight["content_hash"],
        "confidence_basis": insight.get("confidence_basis", {}),
        "importance": insight.get("importance"),
        "sources": insight.get("sources", []),
        "evidence": insight.get("evidence", []),
        "detected_at": insight.get("detected_at"),
    }
    item = {
        "type": "insight",
        "title": _bounded_text(insight["title"], 500),
        "content": _bounded_text(insight["summary"], 50000),
        "data": data,
        "tags": tags[:48] + ["information-radar", "insight"],
        "entities": entities[:50],
        "sensitivity": "normal",
        "status": "active",
        "occurred_at": insight.get("detected_at"),
        "last_verified_at": insight.get("detected_at"),
        "source_item_id": "radar:%s:r%s" % (insight["insight_id"], insight.get("revision") or 1),
        "derived_from": [],
    }
    if insight.get("confidence") is not None:
        item["confidence"] = insight["confidence"]
    if source_uri:
        item["source_uri"] = source_uri
    # The Hub contract hashes the normalized item payload, not the Radar
    # revision hash.  Keep both values visible to make mismatches diagnosable.
    item["content_hash"] = hub_content_hash(item)
    return item


class _JsonHttpClient:
    def __init__(self, base_url: str, api_key: str = "", timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(self, method: str, path: str, payload: Dict[str, Any], operation_key: str = "") -> Dict[str, Any]:
        if not self.base_url:
            raise IntegrationError("DEPENDENCY_UNAVAILABLE", "integration URL is not configured")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        if operation_key:
            headers["Idempotency-Key"] = operation_key
        body = None if method in ("GET", "HEAD") else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return {"http_status": response.status}
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError:
                    value = {"text": raw[:2000]}
                return value if isinstance(value, dict) else {"value": value, "http_status": response.status}
        except HTTPError as error:
            body = ""
            try:
                body = error.read().decode("utf-8")[:1000]
            except Exception:
                pass
            raise IntegrationError("HTTP_%s" % error.code, body or "integration returned HTTP %s" % error.code, unknown=error.code >= 500)
        except (TimeoutError, URLError, OSError) as error:
            raise IntegrationError("DELIVERY_UNKNOWN", "%s: %s" % (type(error).__name__, error), unknown=True)


class ContextHubPublicationClient:
    """Adapter for the service-only Radar publication command."""

    def __init__(self, base_url: str = "", api_key: str = "", timeout: float = 15.0, path: str = ""):
        self.client = _JsonHttpClient(
            base_url or os.getenv("CONTEXTHUB_BASE_URL", os.getenv("CONTEXT_HUB_URL", "")),
            api_key or os.getenv("CONTEXTHUB_API_KEY", ""),
            timeout,
        )
        self.path = path or os.getenv("RADAR_HUB_PUBLICATION_PATH", "/v1/radar/publications")
        self.source_uri = os.getenv("RADAR_PROJECTION_URI", "")

    def publish(self, insight: Dict[str, Any], operation_key: str) -> Dict[str, Any]:
        item = hub_item_for(insight, self.source_uri)
        hub_hash = item["content_hash"]
        wire_item = {key: value for key, value in item.items() if key not in ("content_hash", "source_item_id")}
        body = {
            "schema_version": 1,
            "insight_id": insight["insight_id"],
            "revision": int(insight["revision"]),
            "operation_key": operation_key,
            "content_hash": insight["content_hash"],
            "hub_content_hash": hub_hash,
            "action": "publish",
            "item": wire_item,
        }
        response = self.client.request("POST", self.path, body, operation_key)
        publication = response.get("publication") if isinstance(response.get("publication"), dict) else {}
        item_response = response.get("item") if isinstance(response.get("item"), dict) else {}
        status = str(response.get("status") or publication.get("status") or item_response.get("trust_state") or "UNKNOWN").upper()
        if status == "CANDIDATE":
            status = "CANDIDATE"
        elif status == "ACCEPTED":
            status = "ACCEPTED"
        elif status in ("REJECTED", "REVOKED", "WITHDRAWN", "STALE"):
            status = "WITHDRAWN" if status == "REVOKED" else status
        else:
            status = "UNKNOWN"
        return {
            "status": status,
            "publication_id": response.get("publication_id") or publication.get("publication_id"),
            "hub_item_id": response.get("hub_item_id") or publication.get("hub_item_id") or item_response.get("id") or response.get("item_id"),
            "hub_revision": response.get("hub_revision") or response.get("hub_item_revision") or publication.get("hub_revision") or publication.get("hub_item_revision") or item_response.get("revision"),
            "receipt": {"provider": "contexthub", "path": self.path, "response": response},
            "hub_content_hash": hub_hash,
        }

    def withdraw(self, insight: Dict[str, Any], operation_key: str) -> Dict[str, Any]:
        item = hub_item_for(insight, self.source_uri)
        body = {
            "schema_version": 1,
            "insight_id": insight["insight_id"],
            "revision": int(insight["revision"]),
            "operation_key": operation_key,
            "content_hash": insight["content_hash"],
            "action": "withdraw",
        }
        response = self.client.request("POST", self.path, body, operation_key)
        evidence = response.get("hub_withdrawal") if isinstance(response.get("hub_withdrawal"), dict) else response
        status = str(evidence.get("status") or "UNKNOWN").lower()
        mapped = {"applied": "CONFIRMED", "stale": "STALE", "not_found": "NOT_FOUND"}.get(status, "UNKNOWN")
        return {"status": mapped, "receipt": {"provider": "contexthub", "path": self.path, "response": response}}

    def reconcile(self, insight_id: str) -> Dict[str, Any]:
        path = "/v1/radar/publications?%s" % urlencode({"insight_id": insight_id, "limit": 100})
        return self.client.request("GET", path, {})


class HermesEventClient:
    """At-least-once Radar event delivery with receipt-aware results."""

    def __init__(self, url: str = "", api_key: str = "", timeout: float = 15.0, path: str = ""):
        event_url = url or os.getenv("HERMES_EVENT_URL", "")
        legacy_url = os.getenv("HERMES_WEBHOOK_URL", "")
        self.uses_event_contract = bool(event_url and (url or os.getenv("HERMES_EVENT_URL", "")))
        self.url = event_url or legacy_url
        self.path = path or os.getenv("HERMES_EVENT_PATH", "/api/internal/hermes/events" if self.uses_event_contract else "")
        self.client = _JsonHttpClient(self.url, api_key or os.getenv("HERMES_EVENT_API_KEY", ""), timeout)

    def deliver(self, event: Dict[str, Any]) -> Dict[str, Any]:
        body = {"source": SOURCE_ID, "event_id": event["event_id"], "payload": event} if self.path else event
        response = self.client.request("POST", self.path, body, event["event_id"])
        event_record = response.get("event") if isinstance(response.get("event"), dict) else {}
        receipt_id = response.get("receipt_id") or response.get("delivery_id") or event_record.get("event_id") or (event["event_id"] if response.get("accepted") else None)
        if not receipt_id:
            return {"status": "UNKNOWN", "error": "PROVIDER_RECEIPT_MISSING", "receipt": {"provider": "hermes", "response": response}}
        return {
            "status": "ACCEPTED_BY_HERMES" if self.path else "SENT",
            "receipt": {
                "provider": "hermes",
                "receipt_id": receipt_id,
                "destination_ref": response.get("destination_ref", "hermes_durable_inbox" if self.path else "hermes"),
                "accepted_at": response.get("accepted_at") or _now(),
                "replayed": bool(response.get("replayed", False)),
                "response": response,
            },
        }


class InsightLifecycle:
    def __init__(self, storage: Storage, hub=None, hermes=None):
        self.storage = storage
        self.hub = hub or ContextHubPublicationClient()
        self.hermes = hermes or HermesEventClient()

    def record(self, value: Dict[str, Any]) -> Dict[str, Any]:
        candidate = dict(value)
        candidate.setdefault("detected_at", _now())
        candidate.setdefault("status", "ACTIVE")
        if candidate["status"] != "ACTIVE":
            raise ValueError("INSIGHT_STATUS_NOT_WRITABLE")
        calculated = insight_hash(candidate)
        if candidate.get("content_hash") and candidate["content_hash"] != calculated:
            raise ValueError("INSIGHT_CONTENT_HASH_MISMATCH")
        candidate["content_hash"] = calculated
        return self.storage.save_insight(candidate)

    def publish(self, insight_id: str, revision: Optional[int] = None, operation_key: str = "") -> Dict[str, Any]:
        insight = self.storage.get_insight(insight_id, revision)
        if not insight:
            raise KeyError("INSIGHT_NOT_FOUND")
        publication_key = operation_key or "radar:publish:%s:r%s" % (insight_id, insight["revision"])
        item = hub_item_for(insight)
        payload_hash = publication_hash({"action": "publish", "insight": insight, "item": item})
        publication = self.storage.save_publication({"insight_id": insight_id, "insight_revision": insight["revision"], "action": "publish", "operation_key": publication_key, "payload_hash": payload_hash, "hub_content_hash": item["content_hash"], "status": "PENDING"})
        if publication.get("status") in ("CANDIDATE", "ACCEPTED") and publication.get("hub_item_id"):
            return publication
        try:
            result = self.hub.publish(insight, publication_key)
            return self.storage.update_publication(publication["publication_id"], status=result["status"], hub_item_id=result.get("hub_item_id"), hub_revision=result.get("hub_revision"), receipt=result.get("receipt"), error=None if result["status"] in ("CANDIDATE", "ACCEPTED") else "HUB_PUBLICATION_STATUS_UNKNOWN")
        except IntegrationError as error:
            return self.storage.update_publication(publication["publication_id"], status="UNKNOWN" if error.unknown else "FAILED", receipt={"provider": "contexthub", "error_code": error.code}, error=error.code + ": " + str(error))

    def withdraw(self, insight_id: str, operation_key: str = "") -> Dict[str, Any]:
        insight = self.storage.withdraw_insight(insight_id)
        publication = self.storage.latest_publication(insight_id, "publish")
        key = operation_key or "radar:withdraw:%s:r%s" % (insight_id, insight["revision"])
        withdrawal = None
        if publication:
            withdrawal_hash = publication_hash({"action": "withdraw", "insight": insight, "published_revision": publication.get("insight_revision")})
            withdrawal = self.storage.save_publication({"insight_id": insight_id, "insight_revision": insight["revision"], "action": "withdraw", "operation_key": key, "payload_hash": withdrawal_hash, "status": "PENDING"})
            try:
                result = self.hub.withdraw(insight, key)
                withdrawal = self.storage.update_publication(withdrawal["publication_id"], status="WITHDRAWN", hub_withdrawal_status=result["status"], receipt=result.get("receipt"), error=None if result["status"] in ("CONFIRMED", "STALE", "NOT_FOUND") else "HUB_WITHDRAWAL_STATUS_UNKNOWN")
            except IntegrationError as error:
                withdrawal = self.storage.update_publication(withdrawal["publication_id"], status="UNKNOWN", hub_withdrawal_status="UNKNOWN", receipt={"provider": "contexthub", "error_code": error.code}, error=error.code + ": " + str(error))
        event = self.enqueue_event(insight_id, insight["revision"], event_type="radar.insight.withdrawn.v1", summary="Radar insight withdrawn", action_required=False, expires_at=None)
        return {"insight": insight, "publication": publication, "withdrawal": withdrawal, "event": event}

    def reconcile_publication(self, insight_id: str) -> Dict[str, Any]:
        insight = self.storage.get_insight(insight_id)
        if not insight:
            raise KeyError("INSIGHT_NOT_FOUND")
        response = self.hub.reconcile(insight_id)
        rows = response.get("publications", []) if isinstance(response, dict) else []
        updated = []
        for row in rows:
            if not isinstance(row, dict) or row.get("insight_id") != insight_id:
                continue
            revision = int(row.get("insight_revision") or row.get("revision") or 0)
            action = str(row.get("action") or "publish")
            local = self.storage.publication_for(insight_id, revision, action)
            if not local:
                continue
            status = str(row.get("status", "UNKNOWN")).upper()
            if status == "REVOKED":
                status = "WITHDRAWN"
            if status not in ("CANDIDATE", "ACCEPTED", "REJECTED", "WITHDRAWN", "FAILED", "UNKNOWN", "STALE"):
                status = "UNKNOWN"
            updated.append(self.storage.update_publication(local["publication_id"], status=status, hub_item_id=row.get("hub_item_id"), hub_revision=row.get("hub_item_revision"), hub_withdrawal_status=str(row.get("hub_withdrawal_status", local.get("hub_withdrawal_status", "NOT_REQUESTED"))).upper(), receipt={"provider": "contexthub", "reconciliation": row}, error=None))
        return {"insight_id": insight_id, "publications": updated, "hub_response": response}

    def enqueue_event(self, insight_id: str, revision: Optional[int] = None, event_type: str = "radar.actionable.v1", summary: str = "", priority: str = "normal", action_required: bool = True, expires_at: Optional[str] = None, event_id: str = "", sequence: Optional[int] = None, occurred_at: Optional[str] = None) -> Dict[str, Any]:
        insight = self.storage.get_insight(insight_id, revision)
        if not insight:
            raise KeyError("INSIGHT_NOT_FOUND")
        if event_type != "radar.insight.withdrawn.v1" and insight["status"] == "WITHDRAWN":
            raise ValueError("INSIGHT_WITHDRAWN")
        publication = self.storage.publication_for(insight_id, insight["revision"], "publish")
        prior_event = self.storage.event(event_id) if event_id else None
        if prior_event:
            prior_payload = prior_event.get("payload", {}).get("payload", {})
            occurred_at = occurred_at or prior_event.get("occurred_at")
            expires_at = expires_at if expires_at is not None else prior_event.get("expires_at")
            sequence = sequence if sequence is not None else prior_event.get("sequence")
            summary = summary or prior_payload.get("summary", "")
            priority = priority if priority != "normal" else prior_payload.get("priority", "normal")
            if action_required is True and "action_required" in prior_payload:
                action_required = bool(prior_payload["action_required"])
        event_id = event_id or secrets.token_hex(16)
        sequence = int(sequence or self._next_sequence())
        occurred_at = occurred_at or _now()
        bounded_sources = []
        for source in insight.get("sources", [])[:20]:
            if isinstance(source, dict):
                bounded_sources.append({key: source[key] for key in ("source", "source_item_id", "url", "published_at", "title") if key in source})
        payload = {
            "insight_id": insight["insight_id"],
            "insight_revision": insight["revision"],
            "summary": _bounded_text(summary or insight["summary"]),
            "title": _bounded_text(insight["title"], 500),
            "sources": bounded_sources,
            "priority": priority,
            "action_required": bool(action_required),
            "expires_at": expires_at,
            "publication": {"status": publication.get("status") if publication else "NOT_REQUESTED", "hub_item_id": publication.get("hub_item_id") if publication else None, "hub_revision": publication.get("hub_revision") if publication else None},
            "is_execution_authorization": False,
        }
        envelope = {
            "event_id": event_id,
            "type": event_type,
            "schema_version": 1,
            "source": SOURCE_ID,
            "subject": "insight/%s" % insight["insight_id"],
            "source_epoch": 1,
            "sequence": sequence,
            "subject_revision": insight["revision"],
            "correlation_id": insight["insight_id"],
            "causation_id": "insight/%s/r%s" % (insight["insight_id"], insight["revision"]),
            "occurred_at": occurred_at,
            "expires_at": expires_at,
            "payload": payload,
        }
        value = {"event_id": event_id, "event_type": event_type, "insight_id": insight["insight_id"], "insight_revision": insight["revision"], "source_epoch": 1, "sequence": sequence, "correlation_id": insight["insight_id"], "occurred_at": occurred_at, "expires_at": expires_at, "payload": envelope, "payload_hash": event_hash(envelope)}
        return self.storage.create_event(value)

    def deliver_event(self, event_id: str, allow_unknown_retry: bool = False) -> Dict[str, Any]:
        event = self.storage.event(event_id)
        if not event:
            raise KeyError("EVENT_NOT_FOUND")
        if event.get("outbox_state") in ("UNKNOWN", "SENDING") and not allow_unknown_retry:
            return dict(event, delivery_blocked="UNKNOWN_REQUIRES_RECONCILIATION")
        if event.get("outbox_state") == "WITHDRAWN":
            return event
        expires_at = event.get("expires_at")
        if _is_expired(expires_at) and event.get("event_type") != "radar.insight.withdrawn.v1":
            return self.storage.update_event_delivery(event_id, "EXPIRED", error="EVENT_EXPIRED")
        try:
            # SENDING is durable evidence that a provider call was in flight.
            # A crash at this boundary must be reconciled explicitly, never
            # treated as a safe automatic retry.
            self.storage.update_event_delivery(event_id, "SENDING")
            result = self.hermes.deliver(event["payload"])
            return self.storage.update_event_delivery(event_id, result.get("status", "UNKNOWN"), receipt=result.get("receipt"), error=result.get("error"), increment_attempt=True)
        except IntegrationError as error:
            return self.storage.update_event_delivery(event_id, "UNKNOWN" if error.unknown else "FAILED", receipt={"provider": "hermes", "error_code": error.code}, error=error.code + ": " + str(error), increment_attempt=True)

    def _next_sequence(self) -> int:
        row = self.storage.connection.execute("SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM radar_events").fetchone()
        return int(row["next_sequence"])

    def projection(self, topic_id: Optional[str] = None) -> Dict[str, Any]:
        insights = self.storage.latest_insights(topic_id, 100)
        projected = []
        for insight in insights:
            publication = self.storage.publication_for(insight["insight_id"], insight["revision"], "publish")
            withdrawal = self.storage.latest_publication(insight["insight_id"], "withdraw")
            events = [event for event in self.storage.latest_events(200) if event and event["insight_id"] == insight["insight_id"] and int(event["insight_revision"]) == int(insight["revision"])]
            projected.append({
                "insight_id": insight["insight_id"],
                "revision": insight["revision"],
                "topic_id": insight["topic_id"],
                "title": insight["title"],
                "summary": insight["summary"],
                "sources": insight["sources"],
                "detected_at": insight["detected_at"],
                "confidence": insight["confidence"],
                "importance": insight["importance"],
                "tags": insight["tags"],
                "entities": insight["entities"],
                "content_hash": insight["content_hash"],
                "status": insight["status"],
                "publication": {"status": publication.get("status") if publication else "NOT_REQUESTED", "hub_item_id": publication.get("hub_item_id") if publication else None, "hub_revision": publication.get("hub_revision") if publication else None},
                "withdrawal": {"status": withdrawal.get("status") if withdrawal else "NOT_REQUESTED", "hub_withdrawal_status": withdrawal.get("hub_withdrawal_status") if withdrawal else "NOT_REQUESTED", "receipt": _receipt_summary(withdrawal.get("receipt")) if withdrawal else None},
                "events": [{"event_id": event["event_id"], "type": event["event_type"], "revision": event["insight_revision"], "status": event.get("outbox_state") or event["status"], "receipt": _receipt_summary(event.get("receipt"))} for event in events],
            })
        data = {"topic_id": topic_id, "insights": projected, "raw_data": "radar_owned_not_projected"}
        return {"schema_version": 1, "source_id": SOURCE_ID, "source_revision": "radar:%s" % sha256_json(data), "observed_at": _now(), "last_success_at": _now(), "freshness": "FRESH", "data": data, "error": None}
