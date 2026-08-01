from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import Settings
from src.llm import LLMConfigurationError, LLMResponseError, OpenRouterClient


class FakeCompletions:
    def __init__(self, content: str | None = "done") -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeOpenAI:
    def __init__(self, content: str | None = "done") -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def test_openrouter_uses_expected_multimodal_request_shape(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_model="qwen/qwen3.6-35b-a3b",
        openrouter_http_referer="https://example.com/terminal-hire",
        openrouter_app_title="Terminal-Hire",
    )
    fake = FakeOpenAI("A photo and a video")
    provider = OpenRouterClient(settings, client=fake)

    result = provider.complete(
        "What is in this image and video?",
        image_urls=["https://example.com/photo.jpg"],
        video_urls=["https://example.com/video.mp4"],
    )

    assert result == "A photo and a video"
    assert fake.completions.calls == [
        {
            "extra_headers": {
                "HTTP-Referer": "https://example.com/terminal-hire",
                "X-OpenRouter-Title": "Terminal-Hire",
            },
            "extra_body": {},
            "model": "qwen/qwen3.6-35b-a3b",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What is in this image and video?",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.com/photo.jpg"},
                        },
                        {
                            "type": "video_url",
                            "video_url": {"url": "https://example.com/video.mp4"},
                        },
                    ],
                }
            ],
        }
    ]


def test_openrouter_requires_api_key(tmp_path) -> None:
    with pytest.raises(LLMConfigurationError, match="OPENROUTER_API_KEY"):
        OpenRouterClient(
            Settings(data_dir=tmp_path, openrouter_api_key=None),
            client=FakeOpenAI(),
        )


def test_openrouter_rejects_local_media_paths(tmp_path) -> None:
    provider = OpenRouterClient(
        Settings(data_dir=tmp_path, openrouter_api_key="test-key"),
        client=FakeOpenAI(),
    )

    with pytest.raises(ValueError, match="Image input"):
        provider.complete("Describe this", image_urls=["C:/private/resume.png"])


def test_openrouter_requires_text_response(tmp_path) -> None:
    provider = OpenRouterClient(
        Settings(data_dir=tmp_path, openrouter_api_key="test-key"),
        client=FakeOpenAI(None),
    )

    with pytest.raises(LLMResponseError, match="no text content"):
        provider.complete("Hello")


def test_openrouter_key_is_masked_in_settings(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, openrouter_api_key="very-secret-key")

    assert "very-secret-key" not in repr(settings)
