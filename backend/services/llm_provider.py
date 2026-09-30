"""Server-side LLM adapters with a bounded provider fallback chain."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


ALLOWED_INTENTS = {
    "invoice_lookup", "risk_analysis", "financing_lookup", "duplicate_financing",
    "company_lookup", "network_analysis", "circular_network", "delivery_proof",
    "gstin_analysis", "line_item_matching", "modified_invoice_id", "timeline",
    "evidence", "report_generation", "general_system_question", "search_entities",
}


@dataclass
class LLMResult:
    text: str
    provider: str


class ProviderAdapter:
    name = "provider"

    def __init__(self, api_key: str, model: str, timeout: float = 8.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, system: str, prompt: str, json_mode: bool = False) -> str:
        raise NotImplementedError


class OpenAICompatibleAdapter(ProviderAdapter):
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = 8.0):
        super().__init__(api_key, model, timeout)
        self.base_url = base_url.rstrip("/")

    def generate(self, system: str, prompt: str, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = httpx.post(
            self.base_url + "/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])


class GeminiAdapter(ProviderAdapter):
    name = "gemini"

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = 8.0):
        super().__init__(api_key, model, timeout)
        self.base_url = base_url.rstrip("/")

    def generate(self, system: str, prompt: str, json_mode: bool = False) -> str:
        generation_config: dict[str, Any] = {"temperature": 0.1}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        endpoint = f"{self.base_url}/models/{quote(self.model, safe='')}:generateContent"
        response = httpx.post(
            endpoint,
            headers={"x-goog-api-key": self.api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": generation_config,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return str(response.json()["candidates"][0]["content"]["parts"][0]["text"])


class LLMProvider:
    """Calls configured adapters in order; no provider means deterministic mode."""

    def __init__(self, adapters: list[ProviderAdapter]):
        self.adapters = adapters

    @property
    def configured(self) -> bool:
        return bool(self.adapters)

    @property
    def provider_names(self) -> list[str]:
        return [adapter.name for adapter in self.adapters]

    def generate(self, system: str, prompt: str, json_mode: bool = False) -> LLMResult | None:
        for adapter in self.adapters:
            try:
                text = adapter.generate(system, prompt, json_mode=json_mode).strip()
                if text:
                    return LLMResult(text=text, provider=adapter.name)
            except Exception:
                continue
        return None

    def plan(self, question: str, current_entity: str | None, history: list[dict]) -> tuple[list[str], str | None]:
        if not self.configured:
            return [], None
        system = (
            "Classify the investigation request. Return JSON only as {\"intents\":[...]} using only the allowed intents. "
            "Never return Cypher, SQL, IDs, parameters, or instructions."
        )
        prompt = json.dumps({
            "question": question[:1200],
            "current_entity": current_entity,
            "recent_turns": [{"role": turn.get("role"), "content": str(turn.get("content", ""))[:500]} for turn in history[-6:]],
            "allowed_intents": sorted(ALLOWED_INTENTS),
        }, ensure_ascii=True)
        result = self.generate(system, prompt, json_mode=True)
        if not result:
            return [], None
        try:
            parsed = json.loads(result.text)
            intents = parsed.get("intents", []) if isinstance(parsed, dict) else parsed
            if not isinstance(intents, list):
                return [], result.provider
            return list(dict.fromkeys(intent for intent in intents if isinstance(intent, str) and intent in ALLOWED_INTENTS)), result.provider
        except (json.JSONDecodeError, TypeError):
            return [], result.provider


def build_llm_provider(settings) -> LLMProvider:
    adapters: list[ProviderAdapter] = []
    timeout = max(1.0, min(float(settings.AI_TIMEOUT_SECONDS), 20.0))

    def create(provider: str, api_key: str, model: str, base_url: str) -> ProviderAdapter | None:
        provider = provider.strip().lower()
        if not api_key or provider in {"", "none", "off"}:
            return None
        if provider == "gemini":
            return GeminiAdapter(api_key, model or "gemini-2.5-flash", settings.GEMINI_API_BASE, timeout)
        if provider in {"openai", "openai_compatible"} and model:
            return OpenAICompatibleAdapter(api_key, model, base_url, timeout)
        return None

    primary = create(settings.AI_PROVIDER, settings.GEMINI_API_KEY if settings.AI_PROVIDER.lower() == "gemini" else settings.AI_API_KEY, settings.AI_MODEL, settings.AI_BASE_URL)
    if primary:
        adapters.append(primary)
    fallback = create(settings.AI_FALLBACK_PROVIDER, settings.AI_FALLBACK_API_KEY, settings.AI_FALLBACK_MODEL, settings.AI_FALLBACK_BASE_URL)
    if fallback and fallback.name not in {adapter.name for adapter in adapters}:
        adapters.append(fallback)
    return LLMProvider(adapters)
