from datetime import datetime, timedelta, timezone

from .models import RawSignal


def _github(name, title, body, stars, when, suffix):
    return RawSignal(source="github", source_item_id="%s-%s" % (name, suffix), source_url="https://github.com/demo/%s" % name, title="demo/%s" % name, body=body, published_at=when, collected_at=when, engagement={"stars": stars, "forks": max(1, stars // 12), "issues": 3}, metadata={"repo_name": "demo/%s" % name, "topics": ["ai", "tool"]})


def demo_signals(topic_id: str):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if topic_id == "housing":
        return [
            RawSignal("rss", "beituo-1", "https://example.com/housing/beituo", "北投新案與學區生活圈成交增加", "北投住宅 實價登錄 學區 捷運 成交", published_at=now - timedelta(hours=2), collected_at=now - timedelta(hours=2), engagement={"score": 86}, metadata={"product_name": "北投學區生活圈", "official_url": "https://example.com/housing/beituo"}),
            RawSignal("rss", "beituo-2", "https://example.com/housing/beituo", "北投新案與學區生活圈新增掛牌", "北投住宅 新成屋 學區 重劃區", published_at=now - timedelta(days=1), collected_at=now - timedelta(days=1), engagement={"score": 58}, metadata={"product_name": "北投學區生活圈", "official_url": "https://example.com/housing/beituo"}),
            RawSignal("rss", "songshan-1", "https://example.com/housing/songshan", "松山租金市場出現初步變化", "松山住宅 租金 成交", published_at=now - timedelta(days=2), collected_at=now - timedelta(days=2), engagement={"score": 34}, metadata={"product_name": "松山租賃市場", "official_url": "https://example.com/housing/songshan"}),
        ]
    return [
        _github("omlx", "demo/omlx", "local llm inference server for Apple Silicon", 200, now - timedelta(days=2), "old"),
        _github("omlx", "demo/omlx", "local llm inference server for Apple Silicon", 290, now - timedelta(days=1), "mid"),
        _github("omlx", "demo/omlx", "local llm inference server for Apple Silicon", 620, now, "new"),
        _github("stable-tool", "demo/stable-tool", "agent prompt utility", 10000, now - timedelta(days=2), "old"),
        _github("stable-tool", "demo/stable-tool", "agent prompt utility", 10008, now - timedelta(days=1), "mid"),
        _github("stable-tool", "demo/stable-tool", "agent prompt utility", 10012, now, "new"),
        _github("agent-forge", "demo/agent-forge", "multi agent orchestration and coding agent workflows", 40, now - timedelta(days=1), "github"),
        RawSignal("hackernews", "demo-agent-forge", "https://news.ycombinator.com/item?id=demo-agent-forge", "Show HN: Agent Forge for local agent orchestration", "multi agent orchestration coding agent", published_at=now, collected_at=now, engagement={"score": 76, "comments": 24}, metadata={"product_name": "demo/agent-forge", "story_type": "show_hn"}),
    ]
