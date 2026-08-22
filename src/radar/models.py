from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


@dataclass
class RawSignal:
    source: str
    source_item_id: str
    source_url: str
    title: str
    body: str = ""
    author: str = ""
    published_at: datetime = field(default_factory=utc_now)
    collected_at: datetime = field(default_factory=utc_now)
    engagement: Dict[str, float] = field(default_factory=dict)
    outbound_urls: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def stable_key(self) -> str:
        return "%s:%s" % (self.source, self.source_item_id)


@dataclass
class CollectorResult:
    source: str
    status: str
    signals: List[RawSignal] = field(default_factory=list)
    error: Optional[str] = None
    items_fetched: int = 0
    items_accepted: int = 0


@dataclass
class TopicConfig:
    id: str
    name: str
    description: str
    keywords: List[str]
    categories: List[str]
    digest_max_items: int = 8
    thresholds: Dict[str, int] = field(default_factory=lambda: {"emerging": 45, "rising": 65, "trending": 80})
    source_config: Dict[str, Any] = field(default_factory=dict)
    novelty_days: Dict[str, int] = field(default_factory=lambda: {"new": 1, "emerging": 3, "rising": 7})


@dataclass
class EntityView:
    id: str
    topic_id: str
    name: str
    canonical_name: str
    description: str
    entity_type: str
    official_url: str
    github_url: str
    first_seen_at: datetime
    last_seen_at: datetime
    status: str
    score: float
    trend: str
    category: str
    sources: List[str]
    detected: str
    summary: str
    why: str
    evidence: List[List[str]]
    links: List[List[str]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic_id": self.topic_id,
            "name": self.name,
            "canonical_name": self.canonical_name,
            "description": self.description,
            "entity_type": self.entity_type,
            "official_url": self.official_url,
            "github_url": self.github_url,
            "first_seen_at": isoformat(self.first_seen_at),
            "last_seen_at": isoformat(self.last_seen_at),
            "status": self.status,
            "score": round(self.score),
            "trend": self.trend,
            "category": self.category,
            "sources": self.sources,
            "detected": self.detected,
            "summary": self.summary,
            "why": self.why,
            "evidence": self.evidence,
            "links": self.links,
        }
