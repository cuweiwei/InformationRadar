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
CREATE INDEX IF NOT EXISTS idx_entity_signals_entity ON entity_signals(entity_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_entity_time ON metric_snapshots(entity_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_scores_entity_time ON scores(entity_id, scored_at);
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
        required = {"raw_signals", "entities", "scores", "digests", "delivery_runs"}
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
