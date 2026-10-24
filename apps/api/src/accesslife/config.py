from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://accesslife:accesslife_local@127.0.0.1:5432/accesslife"
    app_public_url: str = "http://localhost:3000"
    app_env: str = "development"
    generation_provider: str = "vertex_ai"
    generation_fallback: str = "groq"
    vertex_ai_model: str = "gemini-3.8-flash"
    vertex_ai_location: str = "global"
    gcp_project_id: str = "project-bb13ecd8-9d67-408d-9a7"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    openai_api_key: str = ""
    openai_model: str = ""
    ollama_api_key: str = ""
    ollama_model: str = ""
    ollama_base_url: str = "http://localhost:11434/v1"
    qloo_api_key: str = ""
    qloo_api_key_secret: str = ""
    qloo_cache_enabled: bool = True
    groq_api_key_secret: str = ""
    openai_api_key_secret: str = ""
    ollama_api_key_secret: str = ""
    tfl_api_key_secret: str = ""
    idfm_api_key_secret: str = ""
    cta_api_key_secret: str = ""
    vbb_api_key_secret: str = ""
    mta_bus_api_key_secret: str = ""
    qloo_base_url: str = "https://hackathon.api.qloo.com"
    taste_provider: str = "development"
    live_providers: bool = True
    provider_limits_enabled: bool = True
    max_daily_model_calls: int = 100
    max_daily_planning_runs: int = 200
    task_backend: str = "postgres"
    cloud_tasks_queue: str = ""
    cloud_tasks_invoker_service_account: str = ""
    worker_internal_url: str = ""
    internal_worker_token: str = ""
    session_retention_hours: int = 24
    plan_deadline_seconds: int = 30
    max_active_planning_runs: int = 3
    tfl_api_key: str = ""
    idfm_api_key: str = ""
    cta_api_key: str = ""
    vbb_api_key: str = ""
    mta_bus_api_key: str = ""
    embedding_model_revision: str = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"


@lru_cache
def settings() -> Settings:
    return Settings()
