import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .models import EntityView, RawSignal, TopicConfig, isoformat, utc_now


SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS raw_signals (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    published_at TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    engagement_json TEXT NOT NULL,
    outbound_urls_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE(source, source_item_id)
);
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    description TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    official_url TEXT NOT NULL,
    github_url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE(topic_id, canonical_name)
);
CREATE TABLE IF NOT EXISTS entity_aliases (
    entity_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    confidence REAL NOT NULL,
    UNIQUE(entity_id, alias)
);
CREATE TABLE IF NOT EXISTS entity_signals (
    entity_id TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    classification_json TEXT NOT NULL,
    UNIQUE(entity_id, signal_id)
);
CREATE TABLE IF NOT EXISTS metric_snapshots (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    source TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scores (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    score REAL NOT NULL,
    status TEXT NOT NULL,
    momentum REAL NOT NULL,
    acceleration REAL NOT NULL,
    cross_source REAL NOT NULL,
    novelty REAL NOT NULL,
    relevance REAL NOT NULL,
    source_quality REAL NOT NULL,
    saturation_penalty REAL NOT NULL,
    scored_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS digests (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    digest_date TEXT NOT NULL,
    text TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(topic_id, digest_date)
);
CREATE TABLE IF NOT EXISTS digest_items (
    digest_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    UNIQUE(digest_id, entity_id)
);
CREATE TABLE IF NOT EXISTS collector_runs (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_ms INTEGER,
    items_fetched INTEGER NOT NULL DEFAULT 0,
    items_accepted INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE TABLE IF NOT EXISTS delivery_runs (
    id TEXT PRIMARY KEY,
    digest_id TEXT NOT NULL,
    adapter TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    is_secret INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS insights (
    insight_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    topic_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    confidence_basis_json TEXT NOT NULL,
    confidence REAL,
    importance REAL,
    tags_json TEXT NOT NULL,
    entities_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    previous_revision INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(insight_id, revision),
    UNIQUE(insight_id, content_hash)
);
CREATE TABLE IF NOT EXISTS insight_publications (
    publication_id TEXT PRIMARY KEY,
    insight_id TEXT NOT NULL,
    insight_revision INTEGER NOT NULL,
    action TEXT NOT NULL DEFAULT 'publish',
    operation_key TEXT NOT NULL UNIQUE,
    payload_hash TEXT NOT NULL,
    hub_content_hash TEXT,
    hub_item_id TEXT,
    hub_revision INTEGER,
    status TEXT NOT NULL,
    hub_withdrawal_status TEXT NOT NULL DEFAULT 'NOT_REQUESTED',
    receipt_json TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(insight_id, insight_revision, action)
);
CREATE TABLE IF NOT EXISTS radar_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    insight_id TEXT NOT NULL,
    insight_revision INTEGER NOT NULL,
    source_epoch INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    correlation_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    expires_at TEXT,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
    -- Multiple actionable events may legitimately refer to one insight
    -- revision; event_id is the producer deduplication key.
);
CREATE TABLE IF NOT EXISTS radar_event_outbox (
    event_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    last_error TEXT,
    receipt_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES radar_events(event_id)
);
CREATE TABLE IF NOT EXISTS radar_projection_receipts (
    projection_id TEXT PRIMARY KEY,
    source_revision TEXT NOT NULL,
    operation_key TEXT NOT NULL UNIQUE,
    payload_hash TEXT NOT NULL,
    state TEXT NOT NULL,
    receipt_json TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entity_signals_entity ON entity_signals(entity_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_entity_time ON metric_snapshots(entity_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_scores_entity_time ON scores(entity_id, scored_at);
CREATE INDEX IF NOT EXISTS idx_insights_topic_time ON insights(topic_id, detected_at);
CREATE INDEX IF NOT EXISTS idx_publications_status ON insight_publications(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_radar_events_status ON radar_events(status, occurred_at);
CREATE INDEX IF NOT EXISTS idx_radar_event_outbox_state ON radar_event_outbox(state, available_at);
"""


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class Storage:
    def __init__(self, path: str = "data/radar.db"):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def get_setting(self, key: str) -> str:
        row = self.connection.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""

    def set_setting(self, key: str, value: str, is_secret: bool = True) -> None:
        self.connection.execute(
            "INSERT INTO app_settings(key,value,is_secret,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,is_secret=excluded.is_secret,updated_at=excluded.updated_at",
            (key, value, 1 if is_secret else 0, isoformat(utc_now())),
        )
        self.connection.commit()

    def upsert_topic(self, config: TopicConfig) -> None:
        payload = json.dumps(config.__dict__, ensure_ascii=False)
        now = isoformat(utc_now())
        self.connection.execute(
            "INSERT INTO topics(id,name,config_json,created_at,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, config_json=excluded.config_json, updated_at=excluded.updated_at",
            (config.id, config.name, payload, now, now),
        )
        self.connection.commit()

    def insert_signal(self, signal: RawSignal) -> Tuple[str, bool]:
        signal_id = str(uuid.uuid5(uuid.NAMESPACE_URL, signal.stable_key()))
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO raw_signals(id,source,source_item_id,source_url,title,body,author,published_at,collected_at,engagement_json,outbound_urls_json,metadata_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (signal_id, signal.source, signal.source_item_id, signal.source_url, signal.title, signal.body, signal.author,
             isoformat(signal.published_at), isoformat(signal.collected_at), json.dumps(signal.engagement),
             json.dumps(signal.outbound_urls), json.dumps(signal.metadata, ensure_ascii=False)),
        )
        self.connection.commit()
        row = self.connection.execute("SELECT id FROM raw_signals WHERE source=? AND source_item_id=?", (signal.source, signal.source_item_id)).fetchone()
        return row["id"], cursor.rowcount > 0

    def all_entities_for_topic(self, topic_id: str) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT e.*, (SELECT json_extract(e.metadata_json, '$.github_repo')) AS github_repo, "
            "(SELECT json_extract(e.metadata_json, '$.official_domain')) AS official_domain "
            "FROM entities e WHERE topic_id=? ORDER BY name", (topic_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_entity(self, entity_id: str) -> Optional[sqlite3.Row]:
        return self.connection.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()

    def create_entity(self, topic_id: str, name: str, canonical_name: str, description: str, entity_type: str,
                      official_url: str, github_url: str, first_seen_at: datetime, metadata: Dict[str, Any]) -> str:
        entity_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO entities(id,topic_id,name,canonical_name,description,entity_type,official_url,github_url,first_seen_at,last_seen_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (entity_id, topic_id, name, canonical_name, description, entity_type, official_url, github_url,
             isoformat(first_seen_at), isoformat(first_seen_at), json.dumps(metadata, ensure_ascii=False)),
        )
        self.connection.commit()
        return entity_id

    def touch_entity(self, entity_id: str, signal: RawSignal, description: str = "", official_url: str = "", github_url: str = "", metadata: Optional[Dict[str, Any]] = None) -> None:
        row = self.get_entity(entity_id)
        if not row:
            return
        current_metadata = json.loads(row["metadata_json"] or "{}")
        current_metadata.update(metadata or {})
        self.connection.execute(
            "UPDATE entities SET last_seen_at=?, description=?, official_url=?, github_url=?, metadata_json=? WHERE id=?",
            (isoformat(max(parse_time(row["last_seen_at"]), signal.published_at)), description or row["description"],
             official_url or row["official_url"], github_url or row["github_url"], json.dumps(current_metadata, ensure_ascii=False), entity_id),
        )
        self.connection.commit()

    def link_signal(self, entity_id: str, signal_id: str, confidence: float, classification: Dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO entity_signals(entity_id,signal_id,confidence,classification_json) VALUES(?,?,?,?)",
            (entity_id, signal_id, confidence, json.dumps(classification, ensure_ascii=False)),
        )
        self.connection.commit()

    def add_alias(self, entity_id: str, alias: str, confidence: float) -> None:
        self.connection.execute("INSERT OR IGNORE INTO entity_aliases(entity_id,alias,confidence) VALUES(?,?,?)", (entity_id, alias, confidence))
        self.connection.commit()

    def add_metric_snapshot(self, entity_id: str, source: str, metric: str, value: float, recorded_at: datetime) -> None:
        self.connection.execute(
            "INSERT INTO metric_snapshots(id,entity_id,source,metric,value,recorded_at) VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4()), entity_id, source, metric, value, isoformat(recorded_at)),
        )
        self.connection.commit()

    def metric_history(self, entity_id: str, source: str, metric: str, limit: int = 8) -> List[Tuple[float, datetime]]:
        rows = self.connection.execute(
            "SELECT value, recorded_at FROM metric_snapshots WHERE entity_id=? AND source=? AND metric=? ORDER BY recorded_at DESC LIMIT ?",
            (entity_id, source, metric, limit),
        ).fetchall()
        return [(float(row["value"]), parse_time(row["recorded_at"])) for row in rows]

    def signals_for_entity(self, entity_id: str) -> List[sqlite3.Row]:
        return self.connection.execute(
            "SELECT rs.*, es.confidence, es.classification_json FROM raw_signals rs JOIN entity_signals es ON rs.id=es.signal_id WHERE es.entity_id=? ORDER BY rs.published_at DESC",
            (entity_id,),
        ).fetchall()

    def save_score(self, entity_id: str, values: Dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO scores(id,entity_id,score,status,momentum,acceleration,cross_source,novelty,relevance,source_quality,saturation_penalty,scored_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), entity_id, values["score"], values["status"], values["momentum"], values["acceleration"], values["cross_source"], values["novelty"], values["relevance"], values["source_quality"], values["saturation_penalty"], isoformat(utc_now())),
        )
        self.connection.commit()

    def latest_score(self, entity_id: str) -> Optional[sqlite3.Row]:
        return self.connection.execute("SELECT * FROM scores WHERE entity_id=? ORDER BY scored_at DESC LIMIT 1", (entity_id,)).fetchone()

    def score_history(self, entity_id: str, limit: int = 2) -> List[sqlite3.Row]:
        return self.connection.execute("SELECT * FROM scores WHERE entity_id=? ORDER BY scored_at DESC LIMIT ?", (entity_id, limit)).fetchall()

    def save_digest(self, topic_id: str, digest_date: str, text: str, payload: Dict[str, Any], items: Sequence[Tuple[str, int, float]]) -> str:
        digest_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO digests(id,topic_id,digest_date,text,payload_json,created_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(topic_id,digest_date) DO UPDATE SET text=excluded.text,payload_json=excluded.payload_json,created_at=excluded.created_at",
            (digest_id, topic_id, digest_date, text, json.dumps(payload, ensure_ascii=False), isoformat(utc_now())),
        )
        row = self.connection.execute("SELECT id FROM digests WHERE topic_id=? AND digest_date=?", (topic_id, digest_date)).fetchone()
        actual_id = row["id"]
        self.connection.execute("DELETE FROM digest_items WHERE digest_id=?", (actual_id,))
        self.connection.executemany("INSERT INTO digest_items(digest_id,entity_id,rank,score) VALUES(?,?,?,?)", [(actual_id, entity_id, rank, score) for entity_id, rank, score in items])
        self.connection.commit()
        return actual_id

    def record_collector_run(self, topic_id: str, source: str, status: str, started_at: datetime, ended_at: datetime, fetched: int, accepted: int, error: str = "") -> None:
        self.connection.execute(
            "INSERT INTO collector_runs(id,topic_id,source,status,started_at,ended_at,duration_ms,items_fetched,items_accepted,error) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), topic_id, source, status, isoformat(started_at), isoformat(ended_at), int((ended_at - started_at).total_seconds() * 1000), fetched, accepted, error),
        )
        self.connection.commit()

    def record_delivery(self, digest_id: str, adapter: str, status: str, error: str = "") -> None:
        self.connection.execute("DELETE FROM delivery_runs WHERE digest_id=? AND adapter=? AND status != 'SUCCESS'", (digest_id, adapter))
        existing = self.connection.execute("SELECT status FROM delivery_runs WHERE digest_id=? AND adapter=? ORDER BY created_at DESC LIMIT 1", (digest_id, adapter)).fetchone()
        if existing and existing["status"] == "SUCCESS":
            return
        self.connection.execute("INSERT INTO delivery_runs(id,digest_id,adapter,status,created_at,error) VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), digest_id, adapter, status, isoformat(utc_now()), error))
        self.connection.commit()

    def delivery_status(self, digest_id: str, adapter: str) -> Optional[sqlite3.Row]:
        return self.connection.execute("SELECT * FROM delivery_runs WHERE digest_id=? AND adapter=? ORDER BY created_at DESC LIMIT 1", (digest_id, adapter)).fetchone()

    def latest_delivery(self, topic_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute("SELECT dr.* FROM delivery_runs dr JOIN digests d ON d.id=dr.digest_id WHERE d.topic_id=? ORDER BY dr.created_at DESC LIMIT 1", (topic_id,)).fetchone()
        return dict(row) if row else None

    def health(self) -> Dict[str, Any]:
        self.connection.execute("SELECT 1").fetchone()
        tables = {row["name"] for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"raw_signals", "entities", "scores", "digests", "delivery_runs", "insights", "insight_publications", "radar_events", "radar_event_outbox"}
        return {"database": "ok", "schema_ready": required.issubset(tables), "path": self.path}

    def backup_to(self, destination: str) -> None:
        parent = os.path.dirname(destination)
        if parent:
            os.makedirs(parent, exist_ok=True)
        target = sqlite3.connect(destination)
        try:
            self.connection.backup(target)
        finally:
            target.close()
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
        self.connection.commit()

    def latest_runs(self, topic_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM collector_runs WHERE topic_id=? ORDER BY started_at DESC LIMIT ?", (topic_id, limit)).fetchall()]

    def latest_digest(self, topic_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute("SELECT * FROM digests WHERE topic_id=? ORDER BY digest_date DESC LIMIT 1", (topic_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    # v2 Radar lifecycle -------------------------------------------------
    # These methods intentionally keep source insight, Hub publication and
    # Hermes event delivery in separate ledgers.  Downstream acknowledgements
    # never rewrite the Radar-owned insight content.

    def save_insight(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Persist one immutable insight revision and return its row.

        Replaying the same revision/hash is safe.  A changed payload must use
        a higher revision, and a withdrawn insight can never be resurrected.
        """
        required = ("insight_id", "topic_id", "title", "summary", "detected_at", "content_hash")
        missing = [key for key in required if not value.get(key)]
        if missing:
            raise ValueError("INSIGHT_MISSING_" + "_".join(missing).upper())
        insight_id = str(value["insight_id"])
        content_hash = str(value["content_hash"])
        requested_revision = int(value.get("revision") or 0)
        now = isoformat(utc_now())
        existing_hash = self.connection.execute(
            "SELECT * FROM insights WHERE insight_id=? AND content_hash=?",
            (insight_id, content_hash),
        ).fetchone()
        if existing_hash:
            return self._insight_row(existing_hash)
        latest = self.connection.execute(
            "SELECT * FROM insights WHERE insight_id=? ORDER BY revision DESC LIMIT 1",
            (insight_id,),
        ).fetchone()
        if latest and latest["status"] == "WITHDRAWN":
            raise ValueError("INSIGHT_WITHDRAWN")
        revision = requested_revision or (int(latest["revision"]) + 1 if latest else 1)
        if latest and revision <= int(latest["revision"]):
            raise ValueError("INSIGHT_REVISION_CONFLICT")
        self.connection.execute(
            "INSERT INTO insights(insight_id,revision,topic_id,title,summary,sources_json,detected_at,confidence_basis_json,confidence,importance,tags_json,entities_json,evidence_json,content_hash,status,previous_revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                insight_id, revision, value["topic_id"], value["title"], value["summary"],
                json.dumps(value.get("sources", []), ensure_ascii=False), value["detected_at"],
                json.dumps(value.get("confidence_basis", {}), ensure_ascii=False), value.get("confidence"),
                value.get("importance"), json.dumps(value.get("tags", []), ensure_ascii=False),
                json.dumps(value.get("entities", []), ensure_ascii=False),
                json.dumps(value.get("evidence", []), ensure_ascii=False), content_hash,
                value.get("status", "ACTIVE"), value.get("previous_revision") or (int(latest["revision"]) if latest else None),
                now, now,
            ),
        )
        self.connection.commit()
        return self.get_insight(insight_id, revision) or {}

    @staticmethod
    def _insight_row(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        for column, output in (("sources_json", "sources"), ("confidence_basis_json", "confidence_basis"),
                               ("tags_json", "tags"), ("entities_json", "entities"), ("evidence_json", "evidence")):
            result[output] = json.loads(result.pop(column) or ("[]" if output in ("sources", "tags", "entities", "evidence") else "{}"))
        return result

    def get_insight(self, insight_id: str, revision: Optional[int] = None) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM insights WHERE insight_id=? AND (? IS NULL OR revision=?) ORDER BY revision DESC LIMIT 1",
            (insight_id, revision, revision),
        ).fetchone()
        return self._insight_row(row) if row else None

    def latest_insights(self, topic_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT i.* FROM insights i JOIN (SELECT insight_id, MAX(revision) revision FROM insights GROUP BY insight_id) latest ON latest.insight_id=i.insight_id AND latest.revision=i.revision WHERE (? IS NULL OR i.topic_id=?) ORDER BY i.detected_at DESC LIMIT ?",
            (topic_id, topic_id, limit),
        ).fetchall()
        return [self._insight_row(row) for row in rows]

    def publication_for(self, insight_id: str, revision: int, action: str = "publish") -> Optional[Dict[str, Any]]:
        row = self.connection.execute("SELECT * FROM insight_publications WHERE insight_id=? AND insight_revision=? AND action=?", (insight_id, revision, action)).fetchone()
        return self._publication_row(row)

    def latest_publication(self, insight_id: str, action: str = "publish") -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM insight_publications WHERE insight_id=? AND action=? ORDER BY insight_revision DESC, updated_at DESC LIMIT 1",
            (insight_id, action),
        ).fetchone()
        return self._publication_row(row)

    @staticmethod
    def _publication_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        result = dict(row)
        result["receipt"] = json.loads(result.pop("receipt_json") or "null")
        return result

    def save_publication(self, value: Dict[str, Any]) -> Dict[str, Any]:
        now = isoformat(utc_now())
        existing = self.connection.execute("SELECT * FROM insight_publications WHERE operation_key=?", (value["operation_key"],)).fetchone()
        if existing:
            if (existing["insight_id"], int(existing["insight_revision"]), existing["payload_hash"], existing["hub_content_hash"]) != (value["insight_id"], int(value["insight_revision"]), value["payload_hash"], value.get("hub_content_hash")):
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return self._publication_row(existing) or {}
        action = value.get("action", "publish")
        existing = self.connection.execute("SELECT * FROM insight_publications WHERE insight_id=? AND insight_revision=? AND action=?", (value["insight_id"], value["insight_revision"], action)).fetchone()
        if existing:
            if (existing["payload_hash"], existing["hub_content_hash"]) != (value["payload_hash"], value.get("hub_content_hash")):
                raise ValueError("PUBLICATION_PAYLOAD_CONFLICT")
            return self._publication_row(existing) or {}
        self.connection.execute(
            "INSERT INTO insight_publications(publication_id,insight_id,insight_revision,action,operation_key,payload_hash,hub_content_hash,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (value.get("publication_id") or str(uuid.uuid4()), value["insight_id"], int(value["insight_revision"]), action, value["operation_key"], value["payload_hash"], value.get("hub_content_hash"), value.get("status", "PENDING"), now, now),
        )
        self.connection.commit()
        return self._publication_row(self.connection.execute("SELECT * FROM insight_publications WHERE insight_id=? AND insight_revision=? AND action=?", (value["insight_id"], value["insight_revision"], action)).fetchone()) or {}

    def update_publication(self, publication_id: str, status: Optional[str] = None, hub_item_id: Optional[str] = None,
                           hub_revision: Optional[int] = None, hub_withdrawal_status: Optional[str] = None,
                           receipt: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> Dict[str, Any]:
        row = self.connection.execute("SELECT * FROM insight_publications WHERE publication_id=?", (publication_id,)).fetchone()
        if not row:
            raise KeyError("PUBLICATION_NOT_FOUND")
        updates = []
        params: List[Any] = []
        for column, value in (("status", status), ("hub_item_id", hub_item_id), ("hub_revision", hub_revision), ("hub_withdrawal_status", hub_withdrawal_status), ("last_error", error)):
            if value is not None:
                updates.append(column + "=?"); params.append(value)
        if receipt is not None:
            updates.append("receipt_json=?"); params.append(json.dumps(receipt, ensure_ascii=False))
        updates.append("updated_at=?"); params.append(isoformat(utc_now())); params.append(publication_id)
        self.connection.execute("UPDATE insight_publications SET " + ",".join(updates) + " WHERE publication_id=?", params)
        self.connection.commit()
        return self._publication_row(self.connection.execute("SELECT * FROM insight_publications WHERE publication_id=?", (publication_id,)).fetchone()) or {}

    def create_event(self, value: Dict[str, Any]) -> Dict[str, Any]:
        now = isoformat(utc_now())
        event_id = str(value["event_id"])
        payload_hash = str(value["payload_hash"])
        existing = self.connection.execute("SELECT * FROM radar_events WHERE event_id=?", (event_id,)).fetchone()
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise ValueError("EVENT_ID_CONFLICT")
            return self.event(event_id) or dict(existing)
        self.connection.execute(
            "INSERT INTO radar_events(event_id,event_type,insight_id,insight_revision,source_epoch,sequence,correlation_id,occurred_at,expires_at,payload_json,payload_hash,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event_id, value["event_type"], value["insight_id"], int(value["insight_revision"]), int(value.get("source_epoch", 1)), int(value["sequence"]), value.get("correlation_id", event_id), value["occurred_at"], value.get("expires_at"), json.dumps(value["payload"], ensure_ascii=False), payload_hash, value.get("status", "PENDING"), now, now),
        )
        self.connection.execute("INSERT INTO radar_event_outbox(event_id,state,available_at,updated_at) VALUES(?,?,?,?)", (event_id, "PENDING", now, now))
        self.connection.commit()
        return self.event(event_id) or {}

    def event(self, event_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute("SELECT e.*, o.state AS outbox_state, o.attempts, o.available_at, o.last_error, o.receipt_json FROM radar_events e LEFT JOIN radar_event_outbox o ON o.event_id=e.event_id WHERE e.event_id=?", (event_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        result["receipt"] = json.loads(result.pop("receipt_json") or "null")
        return result

    def latest_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.connection.execute("SELECT event_id FROM radar_events ORDER BY occurred_at DESC LIMIT ?", (limit,)).fetchall()
        return [self.event(row["event_id"]) for row in rows]

    def update_event_delivery(self, event_id: str, state: str, receipt: Optional[Dict[str, Any]] = None, error: Optional[str] = None, increment_attempt: bool = False) -> Dict[str, Any]:
        now = isoformat(utc_now())
        assignments = ["state=?", "updated_at=?"]
        params: List[Any] = [state, now]
        if receipt is not None:
            assignments.append("receipt_json=?"); params.append(json.dumps(receipt, ensure_ascii=False))
        if error is not None:
            assignments.append("last_error=?"); params.append(error)
        if increment_attempt:
            assignments.append("attempts=attempts+1")
        params.append(event_id)
        self.connection.execute("UPDATE radar_event_outbox SET " + ",".join(assignments) + " WHERE event_id=?", params)
        self.connection.execute("UPDATE radar_events SET status=?,updated_at=? WHERE event_id=?", (state, now, event_id))
        self.connection.commit()
        return self.event(event_id) or {}

    def withdraw_insight(self, insight_id: str) -> Dict[str, Any]:
        latest = self.connection.execute("SELECT * FROM insights WHERE insight_id=? ORDER BY revision DESC LIMIT 1", (insight_id,)).fetchone()
        if not latest:
            raise KeyError("INSIGHT_NOT_FOUND")
        if latest["status"] != "WITHDRAWN":
            now = isoformat(utc_now())
            self.connection.execute("UPDATE insights SET status='WITHDRAWN',updated_at=? WHERE insight_id=?", (now, insight_id))
            self.connection.execute("UPDATE radar_events SET status='WITHDRAWN',updated_at=? WHERE insight_id=? AND status IN ('PENDING','EXPIRED')", (now, insight_id))
            self.connection.execute("UPDATE radar_event_outbox SET state='WITHDRAWN',last_error='insight withdrawn',updated_at=? WHERE event_id IN (SELECT event_id FROM radar_events WHERE insight_id=?) AND state IN ('PENDING','FAILED')", (now, insight_id))
            self.connection.commit()
        return self._insight_row(self.connection.execute("SELECT * FROM insights WHERE insight_id=? ORDER BY revision DESC LIMIT 1", (insight_id,)).fetchone())
