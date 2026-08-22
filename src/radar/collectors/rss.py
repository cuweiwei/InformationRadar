import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from ..models import CollectorResult, RawSignal
from .base import Collector


class RSSCollector(Collector):
    source = "rss"

    def discover(self, topic, since):
        feeds = topic.source_config.get("official_feeds", [])
        if not feeds:
            return CollectorResult(self.source, "PARTIAL", error="No official RSS feeds configured for this topic")
        signals = []
        try:
            for feed_url in feeds:
                root = ET.fromstring(self.request_text(feed_url))
                for item in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                    title = self._text(item, "title")
                    link = self._link(item, feed_url)
                    published = self._text(item, "pubDate") or self._text(item, "{http://www.w3.org/2005/Atom}updated")
                    try:
                        when = parsedate_to_datetime(published) if published and "," in published else self.parse_time(published, since)
                    except (TypeError, ValueError):
                        when = self.parse_time(published, since)
                    if when < since or not title:
                        continue
                    signal_id = link or title
                    signals.append(RawSignal(source=self.source, source_item_id=signal_id, source_url=link, title=title,
                                             body=self._text(item, "description"), published_at=when, outbound_urls=[link] if link else [], metadata={"feed_url": feed_url}))
            return CollectorResult(self.source, "SUCCESS", signals, items_fetched=len(signals), items_accepted=len(signals))
        except Exception as error:
            return self.failure("FAILED", error)

    @staticmethod
    def _text(item, tag):
        node = item.find(tag)
        return (node.text or "").strip() if node is not None else ""

    @staticmethod
    def _link(item, feed_url):
        node = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
        if node is None:
            return ""
        return (node.attrib.get("href") or node.text or "").strip()
