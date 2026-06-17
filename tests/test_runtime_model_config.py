from unittest.mock import patch

from src.runtime.secrets import DEFAULT_MODEL_CONFIG, DEFAULT_OPENAI_COMPATIBLE_BASE_URL, NexaSecrets


def _assert_no_disallowed_models(models):
    joined = " ".join(models.values()).lower()
    assert "gpt" not in joined
    assert "claude" not in joined


def test_secrets_default_models_match_supported_config():
    secrets = NexaSecrets.__new__(NexaSecrets)
    secrets._active_config = "default"
    secrets._block_configs = {}
    secrets._flat_configs = {}

    models = secrets.get_model_config()

    assert models == DEFAULT_MODEL_CONFIG
    _assert_no_disallowed_models(models)


def test_agent_uses_configured_strong_model_without_eager_client(monkeypatch):
    monkeypatch.delenv("NEXA_DEBUG", raising=False)

    with patch("src.runtime.agent.nexa_secrets") as mock_secrets, patch("src.runtime.agent.OpenAI") as mock_openai:
        mock_secrets.get_model_config.return_value = DEFAULT_MODEL_CONFIG.copy()

        from src.runtime.agent import NexaAgent

        agent = NexaAgent(name="test_agent", prompt="test")

    assert agent.model == DEFAULT_MODEL_CONFIG["strong"]
    assert agent.client is None
    mock_openai.assert_not_called()


def test_agent_summary_uses_configured_weak_model(monkeypatch):
    monkeypatch.delenv("NEXA_DEBUG", raising=False)

    with patch("src.runtime.agent.nexa_secrets") as mock_secrets:
        mock_secrets.get_model_config.return_value = DEFAULT_MODEL_CONFIG.copy()

        from src.runtime.agent import NexaAgent

        agent = NexaAgent(name="test_agent", prompt="test")

    assert agent._default_summary_model() == DEFAULT_MODEL_CONFIG["weak"]


def test_agent_client_falls_back_to_configured_openai_compatible_base(monkeypatch):
    monkeypatch.delenv("NEXA_DEBUG", raising=False)

    with patch("src.runtime.agent.nexa_secrets") as mock_secrets, patch("src.runtime.agent.OpenAI") as mock_openai:
        mock_secrets.get_model_config.return_value = DEFAULT_MODEL_CONFIG.copy()
        mock_secrets.get_provider_config.return_value = ("test-key", "")
        mock_secrets.get.side_effect = lambda key, default="": default if key == "BASE_URL" else ""

        from src.runtime.agent import NexaAgent

        agent = NexaAgent(name="test_agent", prompt="test")
        agent._get_client()

    mock_openai.assert_called_once_with(api_key="test-key", base_url=DEFAULT_OPENAI_COMPATIBLE_BASE_URL)


def test_agent_openai_provider_uses_configured_compatible_base(monkeypatch):
    monkeypatch.delenv("NEXA_DEBUG", raising=False)

    with patch("src.runtime.agent.nexa_secrets") as mock_secrets, patch("src.runtime.agent.OpenAI") as mock_openai:
        mock_secrets.get_model_config.return_value = {
            **DEFAULT_MODEL_CONFIG,
            "strong": "openai/minimax-m2.5",
        }
        mock_secrets.get_provider_config.return_value = ("test-key", "")
        mock_secrets.get.side_effect = lambda key, default="": ""

        from src.runtime.agent import NexaAgent

        agent = NexaAgent(name="test_agent", prompt="test")
        agent._get_client()

    mock_openai.assert_called_once_with(api_key="test-key", base_url=DEFAULT_OPENAI_COMPATIBLE_BASE_URL)


def test_compactor_uses_configured_weak_model_without_eager_client():
    with patch("src.runtime.compactor.nexa_secrets") as mock_secrets, patch("src.runtime.compactor.OpenAI") as mock_openai:
        mock_secrets.get_model_config.return_value = DEFAULT_MODEL_CONFIG.copy()

        from src.runtime.compactor import ContextCompactor

        compactor = ContextCompactor()

    assert compactor.model == DEFAULT_MODEL_CONFIG["weak"]
    assert compactor._client is None
    mock_openai.assert_not_called()


def test_compactor_client_falls_back_to_configured_openai_compatible_base():
    with patch("src.runtime.compactor.nexa_secrets") as mock_secrets, patch("src.runtime.compactor.OpenAI") as mock_openai:
        mock_secrets.get_model_config.return_value = DEFAULT_MODEL_CONFIG.copy()
        mock_secrets.get_provider_config.return_value = ("test-key", "")
        mock_secrets.get.side_effect = lambda key, default="": ""

        from src.runtime.compactor import ContextCompactor

        compactor = ContextCompactor()
        compactor._get_client()

    mock_openai.assert_called_once_with(api_key="test-key", base_url=DEFAULT_OPENAI_COMPATIBLE_BASE_URL)
