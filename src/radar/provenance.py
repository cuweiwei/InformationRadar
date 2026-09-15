"""Canonical hashing and bounded downstream payload helpers."""

import hashlib
import json
import unicodedata
from typing import Any, Dict


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_normalize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_stable_normalize(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", str(key)): _stable_normalize(value[key]) for key in sorted(value)}
    return value


def stable_json(value: Any) -> str:
    return canonical_json(_stable_normalize(value))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _normalized_label(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).strip().split()).lower()


def _normalized_entity(value: Any) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", str(value or "")).strip().split())
    separator = normalized.find(":")
    if separator <= 0:
        return normalized.lower()
    kind = normalized[:separator].strip().lower()
    identifier = normalized[separator + 1 :].strip().lower()
    return "%s:%s" % (kind, identifier) if identifier else kind


def _normalized_claim_key(value: Any) -> str:
    segments = []
    for raw in unicodedata.normalize("NFKC", str(value or "")).split("/"):
        segment = "_".join(raw.strip().split())
        separator = segment.find(":")
        if separator < 1:
            segments.append(segment.lower())
        else:
            segments.append("%s:%s" % (segment[:separator].strip().lower(), segment[separator + 1 :].strip().lower()))
    return "/".join(item for item in segments if item)


def hub_content_hash(item: Dict[str, Any]) -> str:
    """Match ContextHub's radarHubContentHash canonical field set."""
    tags = sorted(set(_normalized_label(value) for value in item.get("tags", []) if _normalized_label(value)))
    entities = sorted(set(_normalized_entity(value) for value in item.get("entities", []) if _normalized_entity(value)))
    claim_key = item.get("claim_key")
    payload = {
        "type": "insight",
        "title": item.get("title", ""),
        "content": item.get("content", ""),
        "data": item.get("data"),
        "tags": tags,
        "entities": entities,
        "sensitivity": item.get("sensitivity", "normal"),
        "status": item.get("status", "active"),
        "confidence": item.get("confidence"),
        "occurred_at": item.get("occurred_at"),
        "expires_at": item.get("expires_at"),
        "valid_from": item.get("valid_from"),
        "valid_until": item.get("valid_until"),
        "last_verified_at": item.get("last_verified_at"),
        "decay_policy": item.get("decay_policy"),
        "claim_key": _normalized_claim_key(claim_key) if claim_key else None,
        "derived_from": sorted(set(item.get("derived_from", []))),
        "source_uri": item.get("source_uri"),
    }
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def insight_content(value: Dict[str, Any]) -> Dict[str, Any]:
    """Return fields that define an insight revision, excluding its hash."""
    return {
        "topic_id": value.get("topic_id"),
        "title": value.get("title", ""),
        "summary": value.get("summary", ""),
        "sources": value.get("sources", []),
        "detected_at": value.get("detected_at"),
        "confidence_basis": value.get("confidence_basis", {}),
        "confidence": value.get("confidence"),
        "importance": value.get("importance"),
        "tags": value.get("tags", []),
        "entities": value.get("entities", []),
        "evidence": value.get("evidence", []),
    }


def insight_hash(value: Dict[str, Any]) -> str:
    return sha256_json(insight_content(value))


def event_hash(value: Dict[str, Any]) -> str:
    return sha256_json(value)


def publication_hash(value: Dict[str, Any]) -> str:
    return sha256_json(value)
