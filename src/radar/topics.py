import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from .models import EntityView, RawSignal, TopicConfig


@dataclass
class ClassificationResult:
    relevant: bool
    category: str
    confidence: float
    reason: str
    keywords: List[str]


class TopicPlugin:
    """Topic-specific policy. The core pipeline only depends on this contract."""

    config: TopicConfig

    def __init__(self, config: TopicConfig):
        self.config = config

    def discovery_queries(self) -> List[str]:
        return list(self.config.keywords)

    def classify(self, signal: RawSignal) -> ClassificationResult:
        haystack = (signal.title + " " + signal.body + " " + " ".join(signal.metadata.get("topics", []))).lower()
        matches = [keyword for keyword in self.config.keywords if keyword.lower() in haystack]
        excluded = [term for term in self.config.source_config.get("exclude_terms", []) if term.lower() in haystack]
        if excluded and not matches:
            return ClassificationResult(False, "irrelevant", 0.92, "Excluded by topic policy: %s" % ", ".join(excluded), [])
        confidence = min(0.98, 0.55 + (0.12 * len(matches))) if matches else 0.18
        relevant = bool(matches) and confidence >= 0.55
        category = self._category_for(haystack)
        reason = "Matched topic keywords: %s" % ", ".join(matches[:5]) if matches else "No configured topic keyword match"
        return ClassificationResult(relevant, category, confidence, reason, matches[:10])

    def _category_for(self, haystack: str) -> str:
        for category in self.config.categories:
            terms = category.replace("_", " ").split()
            if any(term in haystack for term in terms):
                return category
        return self.config.categories[0] if self.config.categories else "general"

    def enrichment(self, entity: EntityView, signal_count: int, source_count: int, acceleration: float) -> Dict[str, str]:
        source_text = ", ".join(entity.sources)
        return {
            "summary": entity.description or "%s detected across %d source(s)." % (entity.name, source_count),
            "why": "%s appeared across %d source(s) (%s) with %d relevant signal(s); acceleration is %.1fx." % (
                entity.name, source_count, source_text or "unknown", signal_count, max(0.0, acceleration)
            ),
        }


def ai_tools_plugin() -> TopicPlugin:
    return TopicPlugin(TopicConfig(
        id="ai_tools",
        name="AI Tools",
        description="Early signals across AI developer tools, agents, infrastructure and local inference.",
        keywords=["agent", "llm", "mcp", "inference", "coding agent", "model serving", "prompt", "context", "eval"],
        categories=["coding_agent", "agent_infrastructure", "local_llm", "mcp", "inference", "ai_automation"],
        source_config={
            "subreddits": ["LocalLLaMA", "MachineLearning", "artificial", "ChatGPTCoding", "ClaudeAI", "selfhosted"],
            "exclude_terms": ["quarterly revenue", "hired a new executive", "regulation debate"],
            "official_feeds": [],
        },
    ))


def housing_plugin() -> TopicPlugin:
    return TopicPlugin(TopicConfig(
        id="housing",
        name="Housing",
        description="Early signals across housing supply, transactions, rentals, school districts and development.",
        keywords=["預售屋", "新成屋", "實價登錄", "成交", "租金", "學區", "都更", "捷運", "重劃區", "房價", "住宅"],
        categories=["residential_project", "school_district", "transaction", "rental", "urban_development", "infrastructure"],
        source_config={"subreddits": [], "official_feeds": []},
    ))


def test_topic_plugin() -> TopicPlugin:
    return TopicPlugin(TopicConfig(
        id="test_topic",
        name="Test Topic",
        description="Fixture topic used to prove core extensibility.",
        keywords=["signal", "project"],
        categories=["general"],
    ))


class TopicRegistry:
    def __init__(self, plugins: Iterable[TopicPlugin] = ()):
        self._plugins = {plugin.config.id: plugin for plugin in plugins}

    @classmethod
    def default(cls) -> "TopicRegistry":
        return cls([ai_tools_plugin(), housing_plugin(), test_topic_plugin()])

    def register(self, plugin: TopicPlugin) -> None:
        self._plugins[plugin.config.id] = plugin

    def get(self, topic_id: str) -> TopicPlugin:
        if topic_id not in self._plugins:
            raise KeyError("Unknown topic: %s" % topic_id)
        return self._plugins[topic_id]

    def all(self) -> List[TopicPlugin]:
        return list(self._plugins.values())
