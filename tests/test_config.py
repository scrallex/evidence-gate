from __future__ import annotations

from evidence_gate.config import get_settings


def test_settings_default_to_local_backends_and_private_training(monkeypatch) -> None:
    for name in (
        "EVIDENCE_GATE_EMBEDDING_BACKEND",
        "EVIDENCE_GATE_DECISION_BACKEND",
        "EVIDENCE_GATE_REMOTE_INFERENCE_ALLOWED",
        "EVIDENCE_GATE_PUBLIC_MODEL_TRAINING_ALLOWED",
        "EVIDENCE_GATE_AST_CACHE_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.embeddings.provider == "local_structural"
    assert settings.decision_engine.provider == "deterministic"
    assert settings.privacy.remote_inference_allowed is False
    assert settings.privacy.public_model_training_allowed is False
    assert settings.privacy.organizational_memory_sandboxed is True
    assert settings.ast_cache.enabled is True


def test_settings_load_secure_backend_env_overrides(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EVIDENCE_GATE_EMBEDDING_BACKEND", "azure_openai")
    monkeypatch.setenv("EVIDENCE_GATE_EMBEDDING_ENDPOINT", "https://azure.example.openai.azure.com")
    monkeypatch.setenv("EVIDENCE_GATE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    monkeypatch.setenv("EVIDENCE_GATE_EMBEDDING_API_VERSION", "2024-10-21")
    monkeypatch.setenv("EVIDENCE_GATE_DECISION_BACKEND", "ollama")
    monkeypatch.setenv("EVIDENCE_GATE_DECISION_ENDPOINT", "http://127.0.0.1:11434")
    monkeypatch.setenv("EVIDENCE_GATE_DECISION_MODEL", "llama3.1:8b")
    monkeypatch.setenv("EVIDENCE_GATE_REMOTE_INFERENCE_ALLOWED", "true")
    monkeypatch.setenv("EVIDENCE_GATE_AST_CACHE_ROOT", str(tmp_path / "ast-cache"))

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.embeddings.provider == "azure_openai"
    assert settings.embeddings.endpoint == "https://azure.example.openai.azure.com"
    assert settings.embeddings.deployment == "text-embedding-3-large"
    assert settings.embeddings.api_version == "2024-10-21"
    assert settings.decision_engine.provider == "ollama"
    assert settings.decision_engine.endpoint == "http://127.0.0.1:11434"
    assert settings.decision_engine.model == "llama3.1:8b"
    assert settings.privacy.remote_inference_allowed is True
    assert settings.ast_cache.root == tmp_path / "ast-cache"
