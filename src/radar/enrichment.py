import json
import os
from urllib.request import Request, urlopen


class LLMEnricher:
    """Optional OpenAI-compatible enrichment; deterministic scoring stays authoritative."""

    def __init__(self, settings=None):
        settings = settings or {}
        self.url = settings.get("LLM_API_URL") or os.getenv("LLM_API_URL", "")
        self.key = settings.get("LLM_API_KEY") or os.getenv("LLM_API_KEY", "")
        self.model = settings.get("LLM_MODEL") or os.getenv("LLM_MODEL", "")

    @property
    def configured(self):
        return bool(self.url and self.model)

    def enrich(self, entity):
        if not self.configured:
            return entity
        prompt = ("Return JSON with keys summary and why. Keep each under 240 characters. "
                  "Do not invent facts; use only this evidence.\n" + json.dumps({
                      "name": entity.name, "description": entity.description,
                      "sources": entity.sources, "evidence": entity.evidence,
                      "links": entity.links}, ensure_ascii=False))
        payload = {"model": self.model, "temperature": 0.1, "messages": [
            {"role": "system", "content": "You are a cautious research editor."},
            {"role": "user", "content": prompt}]}
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        try:
            request = Request(self.url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urlopen(request, timeout=float(os.getenv("RADAR_HTTP_TIMEOUT", "15"))) as response:
                result = json.loads(response.read().decode("utf-8"))
            parsed = json.loads(result.get("choices", [{}])[0].get("message", {}).get("content", "{}"))
            if isinstance(parsed.get("summary"), str) and parsed["summary"]:
                entity.summary = parsed["summary"][:240]
            if isinstance(parsed.get("why"), str) and parsed["why"]:
                entity.why = parsed["why"][:240]
        except Exception:
            pass
        return entity

    def enrich_many(self, entities):
        return [self.enrich(entity) for entity in entities]
