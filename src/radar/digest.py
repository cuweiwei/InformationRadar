from datetime import date
from typing import Any, Dict, Iterable, List, Tuple

from .models import EntityView


def build_digest(topic, entities: Iterable[EntityView], digest_date: str = "") -> Tuple[str, Dict[str, Any], List[Tuple[str, int, float]]]:
    digest_date = digest_date or date.today().isoformat()
    selected = list(entities)[: topic.config.digest_max_items]
    payload = {
        "type": "information_radar_digest",
        "topic": topic.config.id,
        "topic_name": topic.config.name,
        "date": digest_date,
        "items": [entity.as_dict() for entity in selected],
    }
    lines = ["%s · Morning Digest" % topic.config.name, digest_date, ""]
    sections = [("🔥 Rising Fast", [item for item in selected if item.status in ("RISING", "TRENDING")]),
                ("🆕 New Signals", [item for item in selected if item.status in ("NEW", "EMERGING")]),
                ("👀 Watchlist", [item for item in selected if item.status in ("WATCHLIST", "COOLING")])]
    rank = 0
    items: List[Tuple[str, int, float]] = []
    for heading, group in sections:
        if not group:
            continue
        lines.extend([heading, ""])
        for entity in group:
            rank += 1
            lines.append("#%d %s · Score %d %s" % (rank, entity.name, round(entity.score), "↑" if entity.trend.startswith("+") else ""))
            lines.append("What it is: %s" % entity.summary)
            lines.append("Why Radar detected it: %s" % entity.why)
            lines.append("Status: %s · Sources: %s" % (entity.status, ", ".join(entity.sources) or "unknown"))
            lines.append("")
            items.append((entity.id, rank, entity.score))
    if not selected:
        lines.extend(["No qualifying signals in this run.", "Collectors may be partial; inspect Source Health for details."])
    return "\n".join(lines).strip(), payload, items
