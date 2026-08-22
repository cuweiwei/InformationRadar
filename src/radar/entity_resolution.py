import re
from difflib import SequenceMatcher
from typing import Iterable, Optional, Tuple
from urllib.parse import urlparse

from .models import RawSignal


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (value or "").lower())


def domain(value: str) -> str:
    try:
        host = urlparse(value).netloc.lower().split(":")[0]
        return host.removeprefix("www.")
    except Exception:
        return ""


def github_repo(value: str) -> str:
    match = re.search(r"github\.com/([^/]+/[^/#?]+)", value or "", re.I)
    return match.group(1).rstrip("/") if match else ""


def candidate_name(signal: RawSignal) -> str:
    title = signal.metadata.get("repo_name") or signal.metadata.get("product_name")
    if title:
        return str(title)
    title = re.sub(r"^show hn:\s*", "", signal.title, flags=re.I)
    title = re.sub(r"^\[[^]]+\]\s*", "", title)
    return title.split(" — ")[0].split(" - ")[0].strip()[:120] or "Untitled signal"


def resolve_signal(signal: RawSignal, existing: Iterable[dict]) -> Tuple[str, float]:
    signal_repo = github_repo(signal.source_url) or github_repo(" ".join(signal.outbound_urls))
    signal_domain = domain(signal.source_url)
    generic_source_domains = {"github.com", "news.ycombinator.com", "reddit.com", "www.reddit.com", "x.com", "twitter.com", "example.com"}
    if signal_domain in generic_source_domains:
        signal_domain = ""
    name = normalize_name(candidate_name(signal))
    best_id: Optional[str] = None
    best_confidence = 0.0
    for entity in existing:
        if signal.source_url and entity.get("official_url") == signal.source_url:
            return entity["id"], 1.0
        if signal_repo and signal_repo == entity.get("github_repo"):
            return entity["id"], 0.95
        if signal_domain and signal_domain == entity.get("official_domain"):
            best_id, best_confidence = entity["id"], max(best_confidence, 0.90)
        entity_name = normalize_name(entity.get("canonical_name") or entity.get("name", ""))
        if name and entity_name and name == entity_name:
            best_id, best_confidence = entity["id"], max(best_confidence, 0.80)
        if name and entity_name:
            similarity = SequenceMatcher(None, name, entity_name).ratio()
            if similarity >= 0.90:
                best_id, best_confidence = entity["id"], max(best_confidence, 0.60)
    return (best_id, best_confidence) if best_confidence >= 0.60 else ("", 0.0)
