import os
from urllib.parse import quote_plus

from ..models import CollectorResult, RawSignal
from .base import Collector


class XCollector(Collector):
    source = "x"

    def discover(self, topic, since):
        token = self.setting("X_BEARER_TOKEN")
        if not token:
            return CollectorResult(self.source, "AUTH_REQUIRED", error="X_BEARER_TOKEN is not configured")
        query = " OR ".join(topic.keywords[:5]) + " -is:retweet"
        url = "https://api.x.com/2/tweets/search/recent?max_results=100&tweet.fields=created_at,public_metrics,author_id&query=%s" % quote_plus(query)
        try:
            payload = self.request_json(url, {"Authorization": "Bearer " + token})
            signals = []
            for tweet in payload.get("data", []):
                metrics = tweet.get("public_metrics", {})
                signals.append(RawSignal(source=self.source, source_item_id=tweet.get("id", ""), source_url="https://x.com/i/web/status/%s" % tweet.get("id", ""), title=tweet.get("text", ""), published_at=self.parse_time(tweet.get("created_at")), engagement={"likes": metrics.get("like_count", 0), "shares": metrics.get("retweet_count", 0), "score": metrics.get("like_count", 0) + metrics.get("retweet_count", 0)}, metadata={"author_id": tweet.get("author_id", "")}))
            return CollectorResult(self.source, "SUCCESS", signals, items_fetched=len(signals), items_accepted=len(signals))
        except Exception as error:
            return self.failure("FAILED", error)
