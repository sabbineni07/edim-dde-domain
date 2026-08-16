"""FoundryLLMProvider honors per-invoke endpoint/deployment overrides."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from edim_dde_domain.config import DomainSettings, clear_settings_cache
from edim_dde_domain.llm.foundry import FoundryLLMProvider, clear_foundry_llm_provider_cache


def test_foundry_invoke_uses_config_endpoint_and_deployment():
    clear_settings_cache()
    clear_foundry_llm_provider_cache()
    settings = DomainSettings(
        azure_openai_endpoint="https://global.example.com",
        azure_openai_deployment_name="gpt-global",
    )
    provider = FoundryLLMProvider(settings=settings)

    fake_choice = SimpleNamespace(
        message=SimpleNamespace(content="  hello  ")
    )
    fake_resp = SimpleNamespace(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    with (
        patch(
            "edim_dde_domain.llm.foundry.foundry_token_provider",
            return_value=lambda: "tok",
        ),
        patch("openai.OpenAI", return_value=fake_client) as openai_ctor,
    ):
        # Re-bind token provider after construction (already set); patch invoke path.
        provider._token_provider = lambda: "tok"
        text = provider.invoke(
            [("system", "s"), ("human", "h")],
            config={
                "endpoint": "https://rca.example.com",
                "deployment": "gpt-rca",
            },
        )

    assert text == "hello"
    openai_ctor.assert_called_once()
    assert openai_ctor.call_args.kwargs["base_url"] == (
        "https://rca.example.com/openai/v1"
    )
    create_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == "gpt-rca"


def test_foundry_invoke_falls_back_to_construct_defaults():
    clear_settings_cache()
    clear_foundry_llm_provider_cache()
    settings = DomainSettings(
        azure_openai_endpoint="https://global.example.com",
        azure_openai_deployment_name="gpt-global",
    )
    provider = FoundryLLMProvider(settings=settings)
    provider._token_provider = lambda: "tok"

    fake_choice = SimpleNamespace(message=SimpleNamespace(content="ok"))
    fake_resp = SimpleNamespace(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    with patch("openai.OpenAI", return_value=fake_client) as openai_ctor:
        provider.invoke([("human", "h")], config={"chain": "rca"})

    assert openai_ctor.call_args.kwargs["base_url"] == (
        "https://global.example.com/openai/v1"
    )
    assert (
        fake_client.chat.completions.create.call_args.kwargs["model"]
        == "gpt-global"
    )


def test_foundry_invoke_honors_sampling_knobs():
    clear_settings_cache()
    clear_foundry_llm_provider_cache()
    settings = DomainSettings(
        azure_openai_endpoint="https://global.example.com",
        azure_openai_deployment_name="gpt-global",
    )
    provider = FoundryLLMProvider(settings=settings)
    provider._token_provider = lambda: "tok"

    fake_choice = SimpleNamespace(message=SimpleNamespace(content="ok"))
    fake_resp = SimpleNamespace(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    with patch("openai.OpenAI", return_value=fake_client):
        provider.invoke(
            [("human", "h")],
            config={
                "chain": "explanation",
                "temperature": 0.0,
                "top_p": 0.95,
                "max_tokens": 2048,
                "top_k": 40,
            },
        )

    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["temperature"] == 0.0  # binding wins over explanation 0.2
    assert kwargs["top_p"] == 0.95
    assert kwargs["max_completion_tokens"] == 2048
    assert "max_tokens" not in kwargs
    assert "top_k" not in kwargs  # not sent to OpenAI chat completions
