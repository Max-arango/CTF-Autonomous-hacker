"""Application settings using Pydantic"""
from typing import Optional, List, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class DatabaseSettings(BaseSettings):
    url: str = "postgresql+asyncpg://ctf:ctf@db:5432/ctf"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False


class RedisSettings(BaseSettings):
    url: str = "redis://redis:6379/0"
    max_connections: int = 50
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


class LLMSettings(BaseSettings):
    provider: str = "nemotron"

    # Nemotron
    nemotron_api_key: Optional[str] = None
    nemotron_base_url: str = "https://integrate.api.nvidia.com/v1"
    nemotron_model: str = "nemotron-3-5-lightning-free"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "nemotron-3-5-lightning-free"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4-turbo-preview"

    # Defaults
    max_tokens: int = 8192
    temperature: float = 0.3
    top_p: float = 0.9
    timeout: int = 60


class DockerSettings(BaseSettings):
    network_prefix: str = "ctf"
    registry: str = "local"
    default_memory_limit: str = "2g"
    default_cpu_limit: str = "2.0"
    default_pids_limit: int = 256
    default_shm_size: str = "256m"


class PathSettings(BaseSettings):
    workspace_path: str = "/workspace"
    artifacts_path: str = "/artifacts"
    logs_path: str = "/logs"


class SecuritySettings(BaseSettings):
    api_key: str = "change-this-in-production"
    audit_log_path: str = "/logs/audit.log"
    audit_log_immutable: bool = True
    permission_manager_port: int = 8080
    permission_manager_tls: bool = False
    allowed_networks: List[str] = [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ]


class ObservabilitySettings(BaseSettings):
    metrics_enabled: bool = True
    metrics_port: int = 9090
    tracing_enabled: bool = False
    tracing_endpoint: str = ""


class ExperimentSettings(BaseSettings):
    max_concurrent_experiments: int = 16
    default_timeout: int = 600
    retain_failed: bool = True
    max_history_per_hypothesis: int = 100


class EvidenceSettings(BaseSettings):
    verification_timeout: int = 120
    require_reproducibility: bool = True
    min_confidence_threshold: float = 0.7


class FlagValidationSettings(BaseSettings):
    formats: List[str] = [
        "flag{.*}",
        "CTF{.*}",
        "ctf{.*}",
        "[A-Z0-9]{32}",
        "[a-f0-9]{32}",
    ]
    verify_against_challenge: bool = True
    require_source_attribution: bool = True


class AgentRuntimeSettings(BaseSettings):
    max_agent_depth: int = 4
    max_active_agents: int = 32
    default_timeout: int = 300
    default_token_budget: int = 100000
    max_retries: int = 3
    retry_delay: int = 5


class OrchestratorSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    challenge_triage_enabled: bool = True
    auto_classification: bool = True
    parallel_execution: bool = True
    max_parallel_agents: int = 8


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # System
    system_name: str = "autonomous-ctf-environment"
    system_version: str = "0.1.0"
    mode: str = "JEOPARDY"
    debug: bool = False
    log_level: str = "INFO"

    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    llm: LLMSettings = LLMSettings()
    docker: DockerSettings = DockerSettings()
    paths: PathSettings = PathSettings()
    security: SecuritySettings = SecuritySettings()
    observability: ObservabilitySettings = ObservabilitySettings()
    experiment: ExperimentSettings = ExperimentSettings()
    evidence: EvidenceSettings = EvidenceSettings()
    flag_validation: FlagValidationSettings = FlagValidationSettings()
    agent_runtime: AgentRuntimeSettings = AgentRuntimeSettings()
    orchestrator: OrchestratorSettings = OrchestratorSettings()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()