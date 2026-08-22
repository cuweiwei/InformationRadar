import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TelegramDelivery:
    name = "telegram"

    def __init__(self, token=None, chat_id=None, thread_id=None, settings=None):
        settings = settings or {}
        self.token = token or settings.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or settings.get("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")
        self.thread_id = thread_id or settings.get("TELEGRAM_THREAD_ID") or os.getenv("TELEGRAM_THREAD_ID", "")

    @property
    def configured(self):
        return bool(self.token and self.chat_id)

    def deliver(self, text: str) -> dict:
        if not self.configured:
            return {"status": "SKIPPED", "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured"}
        chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
        for chunk in chunks:
            data = {"chat_id": self.chat_id, "text": chunk, "disable_web_page_preview": "true"}
            if self.thread_id:
                data["message_thread_id"] = self.thread_id
            request = Request("https://api.telegram.org/bot%s/sendMessage" % self.token, data=urlencode(data).encode(), method="POST")
            try:
                with urlopen(request, timeout=15) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    if not result.get("ok"):
                        return {"status": "FAILED", "error": str(result)}
            except Exception as error:
                return {"status": "FAILED", "error": "%s: %s" % (type(error).__name__, error)}
        return {"status": "SUCCESS", "chunks": len(chunks)}
