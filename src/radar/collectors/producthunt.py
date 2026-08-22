import os

from ..models import CollectorResult, RawSignal
from .base import Collector


class ProductHuntCollector(Collector):
    source = "producthunt"

    def discover(self, topic, since):
        token = self.setting("PRODUCT_HUNT_TOKEN")
        if not token:
            return CollectorResult(self.source, "AUTH_REQUIRED", error="PRODUCT_HUNT_TOKEN is not configured")
        query = "query { posts(first: 50, order: RANKING) { edges { node { id name tagline url votesCount commentsCount createdAt topics { edges { node { name } } } } } } }"
        try:
            payload = self.request_json_post("https://api.producthunt.com/v2/api/graphql", {"query": query}, {"Authorization": "Bearer " + token})
            signals = []
            for edge in payload.get("data", {}).get("posts", {}).get("edges", []):
                product = edge.get("node", {})
                product_id = str(product.get("id", ""))
                if not product_id:
                    continue
                topics = [item.get("node", {}).get("name", "") for item in product.get("topics", {}).get("edges", [])]
                signals.append(RawSignal(source=self.source, source_item_id=product_id, source_url=product.get("url", ""), title=product.get("name", ""), body=product.get("tagline", ""), published_at=self.parse_time(product.get("createdAt")), engagement={"score": product.get("votesCount", 0), "comments": product.get("commentsCount", 0)}, metadata={"product_name": product.get("name", ""), "topics": topics}))
            return CollectorResult(self.source, "SUCCESS", signals, items_fetched=len(signals), items_accepted=len(signals))
        except Exception as error:
            return self.failure("FAILED", error)
