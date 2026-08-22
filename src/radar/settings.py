import os
from typing import Dict, List


SETTING_DEFINITIONS = {
    "GITHUB_TOKEN": {"label": "GitHub token", "secret": True, "group": "providers"},
    "PRODUCT_HUNT_TOKEN": {"label": "Product Hunt token", "secret": True, "group": "providers"},
    "X_BEARER_TOKEN": {"label": "X bearer token", "secret": True, "group": "providers"},
    "TELEGRAM_BOT_TOKEN": {"label": "Telegram bot token", "secret": True, "group": "telegram"},
    "TELEGRAM_CHAT_ID": {"label": "Telegram chat ID", "secret": True, "group": "telegram"},
    "TELEGRAM_THREAD_ID": {"label": "Telegram thread ID", "secret": False, "group": "telegram"},
    "HERMES_WEBHOOK_URL": {"label": "Hermes webhook URL", "secret": True, "group": "hermes"},
    "LLM_API_URL": {"label": "LLM API URL", "secret": False, "group": "enrichment"},
    "LLM_API_KEY": {"label": "LLM API key", "secret": True, "group": "enrichment"},
    "LLM_MODEL": {"label": "LLM model", "secret": False, "group": "enrichment"},
}


def allowed_keys() -> List[str]:
    return list(SETTING_DEFINITIONS.keys())


def environment_value(key: str) -> str:
    return os.getenv(key, "")


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return "%s••••%s" % (value[:3], value[-3:])


def status_payload(storage) -> List[Dict]:
    rows = []
    for key, definition in SETTING_DEFINITIONS.items():
        stored = storage.get_setting(key)
        value = stored if stored != "" else environment_value(key)
        rows.append({"key": key, "label": definition["label"], "group": definition["group"], "secret": definition["secret"], "configured": bool(value), "source": "web" if stored != "" else ("environment" if value else "none"), "masked": mask(value) if definition["secret"] else value})
    return rows


def effective_settings(storage) -> Dict[str, str]:
    return {key: (storage.get_setting(key) or environment_value(key)) for key in SETTING_DEFINITIONS}
