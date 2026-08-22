import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..models import CollectorResult, TopicConfig


class Collector:
    source = "unknown"

    def __init__(self):
        self.settings = {}

    def configure(self, settings: Dict[str, str]) -> None:
        self.settings = dict(settings or {})

    def setting(self, key: str) -> str:
        return self.settings.get(key) or os.getenv(key, "")

    def discover(self, topic: TopicConfig, since: datetime) -> CollectorResult:
        raise NotImplementedError

    def request_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        request = Request(url, headers={"User-Agent": "InformationRadar/0.1 (+personal radar)", **(headers or {})})
        timeout = float(os.getenv("RADAR_HTTP_TIMEOUT", "15"))
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def request_json_post(self, url: str, payload: Any, headers: Optional[Dict[str, str]] = None) -> Any:
        request_headers = {"User-Agent": "InformationRadar/0.1 (+personal radar)", "Content-Type": "application/json", **(headers or {})}
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=request_headers, method="POST")
        timeout = float(os.getenv("RADAR_HTTP_TIMEOUT", "15"))
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def request_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        request = Request(url, headers={"User-Agent": "InformationRadar/0.1 (+personal radar)", **(headers or {})})
        timeout = float(os.getenv("RADAR_HTTP_TIMEOUT", "15"))
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def failure(self, status: str, error: Exception) -> CollectorResult:
        return CollectorResult(self.source, status, error="%s: %s" % (type(error).__name__, error))

    @staticmethod
    def parse_time(value: Any, fallback: Optional[datetime] = None) -> datetime:
        fallback = fallback or datetime.now(timezone.utc)
        if not value:
            return fallback
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return fallback

    @staticmethod
    def unix_time(value: Any, fallback: Optional[datetime] = None) -> datetime:
        fallback = fallback or datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (TypeError, ValueError, OSError):
            return fallback
