import hashlib
import json
from typing import Any

import httpx

from config.settings import settings
from src.models import LLMChatRequest, LLMChatResponse


class LLMService:
    def _cache_key(self, request: LLMChatRequest) -> str:
        raw = json.dumps(request.model_dump(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(f"{settings.LLM_PROVIDER}:{raw}".encode("utf-8")).hexdigest()

    def _read_cache(self) -> dict[str, Any]:
        if not settings.LLM_CACHE_PATH.exists():
            return {}
        try:
            return json.loads(settings.LLM_CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_cache(self, cache: dict[str, Any]) -> None:
        settings.LLM_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def chat(self, request: LLMChatRequest) -> LLMChatResponse:
        key = self._cache_key(request)
        cache = self._read_cache()
        if key in cache:
            cached = cache[key]
            cached["cached"] = True
            return LLMChatResponse(**cached)

        if settings.LLM_PROVIDER == "mock":
            response = self._mock_chat(request)
        elif settings.LLM_PROVIDER in {"openai", "deepseek", "ollama", "siliconflow"}:
            response = self._openai_compatible_chat(request)
        elif settings.LLM_PROVIDER == "bedrock":
            response = LLMChatResponse(provider="bedrock", model="not-configured", content="Bedrock 适配入口已预留，请配置 AWS SDK 后启用。")
        else:
            response = self._mock_chat(request)

        cache[key] = response.model_dump()
        self._write_cache(cache)
        return response

    def _mock_chat(self, request: LLMChatRequest) -> LLMChatResponse:
        content = (
            "【Mock LLM】已基于提示词生成运维建议：\n"
            f"系统角色：{request.system[:80]}\n"
            f"用户输入：{request.prompt[:300]}\n"
            "建议：结合 RAG 证据、监控指标和变更记录进行分层排查；高风险动作进入 HITL 审批。"
        )
        return LLMChatResponse(provider="mock", model="mock-aiops", content=content)

    def _provider_config(self) -> tuple[str, str, str]:
        if settings.LLM_PROVIDER == "deepseek":
            return settings.DEEPSEEK_BASE_URL, settings.DEEPSEEK_API_KEY, "deepseek-chat"
        if settings.LLM_PROVIDER == "ollama":
            return settings.OLLAMA_BASE_URL, "ollama", settings.OLLAMA_MODEL
        return settings.OPENAI_BASE_URL, settings.OPENAI_API_KEY, settings.OPENAI_MODEL

    def _openai_compatible_chat(self, request: LLMChatRequest) -> LLMChatResponse:
        base_url, api_key, model = self._provider_config()
        if not api_key and settings.LLM_PROVIDER != "ollama":
            return LLMChatResponse(provider=settings.LLM_PROVIDER, model=model, content="未配置 API Key，已跳过真实 LLM 调用。")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature,
        }
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{base_url.rstrip('/')}/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return LLMChatResponse(provider=settings.LLM_PROVIDER, model=model, content=content)
        except Exception as exc:  # noqa: BLE001 - provider errors should degrade gracefully in demo mode
            return LLMChatResponse(provider=settings.LLM_PROVIDER, model=model, content=f"LLM 调用失败，已降级：{exc}")


llm_service = LLMService()
