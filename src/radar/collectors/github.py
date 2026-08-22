from datetime import datetime, timezone
from urllib.parse import quote_plus

from ..models import CollectorResult, RawSignal
from ..topics import TopicPlugin
from .base import Collector


class GitHubCollector(Collector):
    source = "github"

    def discover(self, topic, since):
        query_terms = topic.keywords[:6]
        query = " OR ".join('"%s"' % term for term in query_terms)
        query += " pushed:>=%s" % since.date().isoformat()
        url = "https://api.github.com/search/repositories?q=%s&sort=updated&order=desc&per_page=50" % quote_plus(query)
        headers = {}
        if self.setting("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + self.setting("GITHUB_TOKEN")
        try:
            payload = self.request_json(url, headers)
            signals = []
            for repo in payload.get("items", []):
                full_name = repo.get("full_name", "")
                if not full_name:
                    continue
                signals.append(RawSignal(
                    source=self.source, source_item_id=full_name, source_url=repo.get("html_url", ""),
                    title=full_name, body=repo.get("description") or "", author=(repo.get("owner") or {}).get("login", ""),
                    published_at=self.parse_time(repo.get("pushed_at")), engagement={"stars": repo.get("stargazers_count", 0), "forks": repo.get("forks_count", 0), "issues": repo.get("open_issues_count", 0)},
                    outbound_urls=[repo.get("homepage", "")] if repo.get("homepage") else [],
                    metadata={"repo_name": full_name, "topics": repo.get("topics", []), "language": repo.get("language") or "", "created_at": repo.get("created_at"), "official_url": repo.get("homepage") or repo.get("html_url", ""), "repo_id": repo.get("id")},
                ))
            return CollectorResult(self.source, "SUCCESS", signals, items_fetched=len(payload.get("items", [])), items_accepted=len(signals))
        except Exception as error:
            status = "RATE_LIMITED" if "403" in str(error) or "429" in str(error) else "FAILED"
            return self.failure(status, error)
