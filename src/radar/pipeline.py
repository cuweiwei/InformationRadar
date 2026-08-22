import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

from .collectors import GitHubCollector, HackerNewsCollector, ProductHuntCollector, RSSCollector, RedditCollector, XCollector
from .digest import build_digest
from .entity_resolution import candidate_name, domain, github_repo, normalize_name, resolve_signal
from .models import EntityView, RawSignal
from .scoring import acceleration, clamp, cross_source_score, early_signal_score, lifecycle, log_scale, novelty_score
from .storage import Storage, parse_time
from .topics import TopicPlugin, TopicRegistry
from .delivery import HermesDelivery, TelegramDelivery
from .settings import effective_settings


class RadarPipeline:
    def __init__(self, storage: Storage, registry: Optional[TopicRegistry] = None, collectors: Optional[Iterable] = None):
        self.storage = storage
        self.registry = registry or TopicRegistry.default()
        self.collectors = list(collectors or [GitHubCollector(), HackerNewsCollector(), RedditCollector(), ProductHuntCollector(), XCollector(), RSSCollector()])

    def run(self, topic_id: str, since: Optional[datetime] = None, deliver: bool = False, dry_run: bool = False) -> Dict:
        topic = self.registry.get(topic_id)
        self.storage.upsert_topic(topic.config)
        settings = effective_settings(self.storage)
        since = since or (datetime.now(timezone.utc) - timedelta(days=1))
        results = []
        for collector in self.collectors:
            collector.configure(settings)
            started = datetime.now(timezone.utc)
            try:
                result = collector.discover(topic.config, since)
            except Exception as error:
                from .models import CollectorResult
                result = CollectorResult(collector.source, "FAILED", error="%s: %s" % (type(error).__name__, error))
            ended = datetime.now(timezone.utc)
            self.storage.record_collector_run(topic_id, result.source, result.status, started, ended, result.items_fetched, result.items_accepted, result.error or "")
            accepted = self.ingest_signals(topic, result.signals, dry_run=dry_run)
            result.items_accepted = accepted
            results.append(result)
        ranked = self.score_topic(topic)
        text, payload, items = build_digest(topic, ranked)
        digest_id = ""
        delivery = {}
        if not dry_run:
            digest_id = self.storage.save_digest(topic_id, payload["date"], text, payload, items)
            if deliver:
                telegram = TelegramDelivery(settings=settings)
                delivery[telegram.name] = telegram.deliver(text)
                self.storage.record_delivery(digest_id, telegram.name, delivery[telegram.name]["status"], delivery[telegram.name].get("error", ""))
                hermes = HermesDelivery(settings=settings)
                delivery[hermes.name] = hermes.deliver(payload)
                self.storage.record_delivery(digest_id, hermes.name, delivery[hermes.name]["status"], delivery[hermes.name].get("error", ""))
        return {"topic": topic_id, "collectors": [{"source": result.source, "status": result.status, "fetched": result.items_fetched, "accepted": result.items_accepted, "error": result.error} for result in results], "entities": len(ranked), "digest_id": digest_id, "digest": text, "delivery": delivery, "partial": any(result.status not in ("SUCCESS", "PARTIAL") for result in results)}

    def verify_connection(self, target: str, delivery_test: bool = False) -> Dict:
        """Verify a configured provider without returning or logging its credential."""
        settings = effective_settings(self.storage)
        try:
            if target == "github":
                collector = GitHubCollector(); collector.configure(settings)
                headers = {"Authorization": "Bearer " + settings["GITHUB_TOKEN"]} if settings.get("GITHUB_TOKEN") else {}
                payload = collector.request_json("https://api.github.com/rate_limit", headers)
                return {"target": target, "status": "SUCCESS", "message": "GitHub API reachable", "rate": payload.get("rate", {})}
            if target == "hackernews":
                HackerNewsCollector().request_json("https://hn.algolia.com/api/v1/search?query=information-radar&hitsPerPage=1")
                return {"target": target, "status": "SUCCESS", "message": "Hacker News API reachable"}
            if target == "reddit":
                RedditCollector().request_json("https://www.reddit.com/r/LocalLLaMA/about.json")
                return {"target": target, "status": "SUCCESS", "message": "Reddit public endpoint reachable"}
            if target == "producthunt":
                result = ProductHuntCollector(); result.configure(settings)
                check = result.discover(self.registry.get("ai_tools").config, datetime.now(timezone.utc) - timedelta(days=1))
                return {"target": target, "status": "SUCCESS" if check.status == "SUCCESS" else check.status, "message": check.error or "Product Hunt API reachable", "items": check.items_fetched}
            if target == "x":
                result = XCollector(); result.configure(settings)
                check = result.discover(self.registry.get("ai_tools").config, datetime.now(timezone.utc) - timedelta(days=1))
                return {"target": target, "status": "SUCCESS" if check.status == "SUCCESS" else check.status, "message": check.error or "X API reachable", "items": check.items_fetched}
            if target == "telegram":
                telegram = TelegramDelivery(settings=settings)
                if not telegram.configured:
                    return {"target": target, "status": "AUTH_REQUIRED", "message": "Telegram bot token and chat ID are not configured"}
                checker = GitHubCollector()
                payload = checker.request_json("https://api.telegram.org/bot%s/getMe" % telegram.token)
                if delivery_test:
                    result = telegram.deliver("Information Radar delivery test ✓\nThis message confirms the configured Telegram destination.")
                    return {"target": target, **result, "message": "Test message sent" if result.get("status") == "SUCCESS" else result.get("error", "Delivery failed")}
                return {"target": target, "status": "SUCCESS" if payload.get("ok") else "FAILED", "message": "Telegram bot authenticated"}
            if target == "hermes":
                hermes = HermesDelivery(settings=settings)
                if not hermes.webhook_url:
                    return {"target": target, "status": "AUTH_REQUIRED", "message": "Hermes webhook URL is not configured"}
                if delivery_test:
                    result = hermes.deliver({"type": "information_radar_delivery_test", "message": "Information Radar delivery test"})
                    return {"target": target, **result, "message": "Test payload sent" if result.get("status") == "SUCCESS" else result.get("error", "Delivery failed")}
                return {"target": target, "status": "CONFIGURED", "message": "Hermes webhook is configured; use delivery test to probe it"}
            return {"target": target, "status": "FAILED", "message": "Unknown verification target"}
        except Exception as error:
            text = "%s: %s" % (type(error).__name__, error)
            return {"target": target, "status": "FAILED", "message": text[:240]}

    def ingest_signals(self, topic: TopicPlugin, signals: Iterable[RawSignal], dry_run: bool = False) -> int:
        accepted = 0
        for signal in signals:
            classification = topic.classify(signal)
            signal_id, inserted = self.storage.insert_signal(signal)
            if not classification.relevant:
                continue
            accepted += 1
            existing = self.storage.all_entities_for_topic(topic.config.id)
            entity_id, confidence = resolve_signal(signal, existing)
            if not entity_id:
                name = signal.metadata.get("repo_name") or signal.metadata.get("product_name") or candidate_name(signal)
                official_url = signal.metadata.get("official_url") or (signal.source_url if signal.source not in ("hackernews", "reddit") else "")
                github_url = signal.source_url if "github.com/" in signal.source_url else ""
                entity_id = self.storage.create_entity(topic.config.id, name, normalize_name(name), signal.body[:500], classification.category, official_url, github_url, signal.published_at, {"github_repo": github_repo(signal.source_url), "official_domain": domain(official_url), "category": classification.category})
                confidence = 0.95 if github_url else 0.80
            else:
                github_url = signal.source_url if "github.com/" in signal.source_url else ""
                self.storage.touch_entity(entity_id, signal, description=signal.body[:500], official_url=signal.metadata.get("official_url", ""), github_url=github_url, metadata={"category": classification.category})
            self.storage.add_alias(entity_id, candidate_name(signal), confidence)
            self.storage.link_signal(entity_id, signal_id, confidence, {"relevant": classification.relevant, "category": classification.category, "confidence": classification.confidence, "reason": classification.reason, "keywords": classification.keywords})
            if not dry_run:
                for metric, value in signal.engagement.items():
                    if isinstance(value, (int, float)):
                        self.storage.add_metric_snapshot(entity_id, signal.source, metric, float(value), signal.collected_at)
        return accepted

    def score_topic(self, topic: TopicPlugin) -> List[EntityView]:
        now = datetime.now(timezone.utc)
        ranked = []
        for row in self.storage.all_entities_for_topic(topic.config.id):
            entity_id = row["id"]
            signals = self.storage.signals_for_entity(entity_id)
            if not signals:
                continue
            sources = sorted(set(signal["source"] for signal in signals))
            total_engagement = 0.0
            velocities = []
            accelerations = []
            source_quality_values = []
            for source in sources:
                metric = "stars" if source == "github" else "score"
                history = self.storage.metric_history(entity_id, source, metric)
                if not history:
                    metric = "likes" if source == "x" else metric
                    history = self.storage.metric_history(entity_id, source, metric)
                if history:
                    total_engagement += history[0][0]
                    from .scoring import velocity
                    velocities.append(velocity(history) * 24)
                    accelerations.append(acceleration(history))
                source_quality_values.append({"github": 90, "hackernews": 88, "reddit": 75, "producthunt": 78, "rss": 82, "x": 60}.get(source, 50))
            momentum = clamp(0.65 * log_scale(sum(velocities), 500) + 0.35 * log_scale(total_engagement, 1000))
            accel_ratio = sum(accelerations) / len(accelerations) if accelerations else 1.0
            acceleration_score = clamp(50.0 + ((accel_ratio - 1.0) * 25.0))
            cross = cross_source_score(len(sources))
            first_seen = parse_time(row["first_seen_at"])
            novelty = novelty_score(first_seen, now)
            confidences = [json.loads(signal["classification_json"]).get("confidence", 0.5) for signal in signals]
            relevance = clamp((sum(confidences) / len(confidences)) * 100.0)
            quality = sum(source_quality_values) / len(source_quality_values)
            saturation = 40.0 if total_engagement > 100000 else 20.0 if len(signals) > 20 else 5.0 if len(signals) > 8 else 0.0
            values = early_signal_score(momentum, acceleration_score, cross, novelty, relevance, quality, saturation)
            values["status"] = lifecycle(values["score"], first_seen, accel_ratio, topic.config.thresholds, now)
            previous = self.storage.score_history(entity_id, 1)
            previous_delta = values["score"] - float(previous[0]["score"]) if previous else 0.0
            trend = "%+d" % round(previous_delta) if previous else ("+%d" % round(max(1, values["score"] * 0.12)))
            links = []
            if row["github_url"]: links.append(["GitHub", row["github_url"]])
            if row["official_url"] and row["official_url"] not in [row["github_url"]]: links.append(["Official", row["official_url"]])
            for signal in signals[:3]:
                if signal["source_url"] and not any(signal["source_url"] == item[1] for item in links):
                    links.append([signal["source"].title(), signal["source_url"]])
            evidence = self._evidence(entity_id, sources, velocities)
            view = EntityView(id=entity_id, topic_id=topic.config.id, name=row["name"], canonical_name=row["canonical_name"], description=row["description"], entity_type=row["entity_type"], official_url=row["official_url"], github_url=row["github_url"], first_seen_at=first_seen, last_seen_at=parse_time(row["last_seen_at"]), status=values["status"], score=values["score"], trend=trend, category=json.loads(row["metadata_json"]).get("category", row["entity_type"]), sources=sources, detected=self._age_label(first_seen, now), summary=row["description"] or "%s detected across multiple signals." % row["name"], why="%s appeared across %d source(s) with %d relevant signal(s); attention is being ranked by momentum and acceleration." % (row["name"], len(sources), len(signals)), evidence=evidence, links=links)
            self.storage.save_score(entity_id, values)
            ranked.append(view)
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    @staticmethod
    def _age_label(first_seen, now):
        hours = max(0, int((now - first_seen).total_seconds() / 3600))
        return "%d hours ago" % hours if hours < 48 else "%d days ago" % round(hours / 24)

    def _evidence(self, entity_id, sources, velocities):
        evidence = []
        for source, velocity_value in zip(sources, velocities or [0]):
            metric_label = "stars / 24h" if source == "github" else "engagement / 24h"
            evidence.append(["+%d" % round(max(0.0, velocity_value)), "%s %s" % (source.title(), metric_label)])
        evidence.append([str(len(sources)), "independent sources"])
        return evidence[:3]
