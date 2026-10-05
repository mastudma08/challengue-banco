from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Onboarding Orchestrator"
    environment: str = "local"
    database_url: str = "sqlite:////tmp/onboarding.db"
    auth_enabled: bool = True
    jwt_secret: str = "local-dev-secret-change-me-32-bytes-minimum"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "onboarding-local"
    jwt_audience: str = "onboarding-api"
    identity_confidence_threshold: float = 0.8
    max_request_bytes: int = 16_384
    policy_corpus_path: str = "docs/policies"

    llm_mode: Literal["mock", "fake", "openai_compatible"] = "fake"
    llm_base_url: str = "http://host.containers.internal:11434"
    llm_api_key: str = "local-placeholder"
    llm_model: str = "local-model"
    llm_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
