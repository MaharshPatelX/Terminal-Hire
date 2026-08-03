"""OpenRouter chat completions through the OpenAI Python client."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import urlparse

from openai import OpenAI

from ..config import Settings


class LLMConfigurationError(ValueError):
    """The selected model provider is not configured for use."""


class LLMResponseError(RuntimeError):
    """The model returned no usable text response."""


class OpenRouterClient:
    """Small OpenRouter adapter with explicit multimodal inputs.

    Local files and profile data are never attached implicitly. Callers must opt in
    to every remote image or video URL included in a request.
    """

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        key = settings.openrouter_api_key
        if key is None or not key.get_secret_value().strip():
            raise LLMConfigurationError(
                "OPENROUTER_API_KEY is required when using OpenRouter"
            )
        if settings.openrouter_timeout_seconds <= 0:
            raise LLMConfigurationError(
                "OPENROUTER_TIMEOUT_SECONDS must be greater than zero"
            )

        self.model = settings.openrouter_model.strip()
        if not self.model:
            raise LLMConfigurationError("OPENROUTER_MODEL cannot be empty")
        self.provider = settings.openrouter_provider.strip()
        if not self.provider:
            raise LLMConfigurationError("OPENROUTER_PROVIDER cannot be empty")
        self.allow_fallbacks = settings.openrouter_allow_fallbacks
        self.http_referer = (settings.openrouter_http_referer or "").strip()
        self.app_title = (settings.openrouter_app_title or "").strip()
        self._client = client or OpenAI(
            base_url=settings.openrouter_base_url.rstrip("/"),
            api_key=key.get_secret_value(),
            timeout=settings.openrouter_timeout_seconds,
        )

    def complete(
        self,
        prompt: str,
        *,
        image_urls: Sequence[str] = (),
        video_urls: Sequence[str] = (),
    ) -> str:
        """Return text for a prompt with optional image and video URL inputs."""
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("The OpenRouter prompt cannot be empty")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend(
            {
                "type": "image_url",
                "image_url": {"url": self._validated_media_url(url, "image")},
            }
            for url in image_urls
        )
        content.extend(
            {
                "type": "video_url",
                "video_url": {"url": self._validated_media_url(url, "video")},
            }
            for url in video_urls
        )

        return self.chat([{"role": "user", "content": content}])

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        json_mode: bool = False,
        model: str | None = None,
        use_configured_provider: bool = True,
    ) -> str:
        """Return one chat response, optionally requiring a JSON object."""
        if not messages:
            raise ValueError("At least one chat message is required")
        selected_model = (model or self.model).strip()
        if not selected_model:
            raise ValueError("The OpenRouter model cannot be empty")
        request: dict[str, Any] = {
            "extra_headers": self._headers(),
            "model": selected_model,
            "messages": messages,
        }
        if use_configured_provider:
            request["extra_body"] = {
                "provider": {
                    "only": [self.provider],
                    "allow_fallbacks": self.allow_fallbacks,
                }
            }
        if json_mode:
            request["response_format"] = {"type": "json_object"}
        completion = self._client.chat.completions.create(
            **request,
        )
        if not completion.choices:
            raise LLMResponseError("OpenRouter returned no completion choices")
        response = completion.choices[0].message.content
        if not isinstance(response, str) or not response.strip():
            raise LLMResponseError("OpenRouter returned no text content")
        return response.strip()

    def check_connection(self) -> str:
        """Make a minimal authenticated model request for the Settings health check."""
        return self.complete("Reply with exactly: OK")

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.app_title:
            headers["X-OpenRouter-Title"] = self.app_title
        return headers

    @staticmethod
    def _validated_media_url(url: str, kind: str) -> str:
        candidate = url.strip()
        parsed = urlparse(candidate)
        is_remote = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        is_data = candidate.startswith(f"data:{kind}/")
        if not is_remote and not is_data:
            raise ValueError(
                f"{kind.title()} input must be an http(s) URL or {kind} data URL"
            )
        return candidate
