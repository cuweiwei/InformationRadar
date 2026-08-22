from urllib.parse import quote_plus

from ..models import CollectorResult, RawSignal
from .base import Collector


class RedditCollector(Collector):
    source = "reddit"

    def discover(self, topic, since):
        subreddits = topic.source_config.get("subreddits", [])
        if not subreddits:
            return CollectorResult(self.source, "PARTIAL", error="No subreddits configured for this topic")
        signals = []
        try:
            for subreddit in subreddits:
                payload = self.request_json("https://www.reddit.com/r/%s/new.json?limit=25" % quote_plus(subreddit))
                for child in payload.get("data", {}).get("children", []):
                    post = child.get("data", {})
                    created = self.unix_time(post.get("created_utc"))
                    if created < since:
                        continue
                    post_id = post.get("id")
                    if not post_id:
                        continue
                    signals.append(RawSignal(
                        source=self.source, source_item_id=post_id, source_url="https://www.reddit.com%s" % post.get("permalink", ""),
                        title=post.get("title") or "", body=post.get("selftext") or "", author=post.get("author") or "[deleted]",
                        published_at=created, engagement={"score": post.get("score", 0), "comments": post.get("num_comments", 0)},
                        outbound_urls=[post.get("url")] if post.get("url") else [], metadata={"subreddit": subreddit, "community": subreddit},
                    ))
            return CollectorResult(self.source, "SUCCESS", signals, items_fetched=len(signals), items_accepted=len(signals))
        except Exception as error:
            status = "RATE_LIMITED" if "429" in str(error) or "403" in str(error) else "FAILED"
            return self.failure(status, error)
