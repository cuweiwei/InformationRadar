import json
import os
from urllib.request import Request, urlopen


class HermesDelivery:
    name = "hermes"

    def __init__(self, webhook_url=None, settings=None):
        settings = settings or {}
        self.webhook_url = webhook_url or settings.get("HERMES_WEBHOOK_URL") or os.getenv("HERMES_WEBHOOK_URL", "")

    def deliver(self, payload: dict) -> dict:
        if not self.webhook_url:
            return {"status": "SKIPPED", "error": "HERMES_WEBHOOK_URL is not configured"}
        try:
            request = Request(self.webhook_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=15) as response:
                return {"status": "SUCCESS", "http_status": response.status}
        except Exception as error:
            return {"status": "FAILED", "error": "%s: %s" % (type(error).__name__, error)}
