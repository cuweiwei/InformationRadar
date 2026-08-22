from urllib.parse import quote_plus

from ..models import CollectorResult, RawSignal
from .base import Collector


class HackerNewsCollector(Collector):
    source = "hackernews"

    def discover(self, topic, since):
        query = " ".join(topic.keywords[:5])
        url = "https://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=created_at_i>%d&hitsPerPage=50&query=%s" % (int(since.timestamp()), quote_plus(query))
        try:
            payload = self.request_json(url)
            signals = []
            for story in payload.get("hits", []):
                object_id = str(story.get("objectID", ""))
                if not object_id:
                    continue
                item_url = story.get("url") or "https://news.ycombinator.com/item?id=%s" % object_id
                signals.append(RawSignal(
                    source=self.source, source_item_id=object_id, source_url=item_url, title=story.get("title") or "",
                    body=story.get("story_text") or "", author=story.get("author") or "", published_at=self.parse_time(story.get("created_at")),
                    engagement={"score": story.get("points") or 0, "comments": story.get("num_comments") or 0},
                    outbound_urls=[story.get("url")] if story.get("url") else [],
                    metadata={"hn_id": object_id, "story_type": "show_hn" if (story.get("title") or "").lower().startswith("show hn") else "story"},
                ))
            return CollectorResult(self.source, "SUCCESS", signals, items_fetched=len(payload.get("hits", [])), items_accepted=len(signals))
        except Exception as error:
            return self.failure("FAILED", error)
