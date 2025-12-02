"""
Configuration management for ContractGuard AI.

Uses pydantic-settings for type-safe configuration with environment variable support.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ContractGuard AI"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Google AI Configuration
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "text-embedding-004"
    google_search_engine_id: str = ""  # For Google Custom Search

    # Vector Database (Weaviate)
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str = ""

    # Object Storage (MinIO)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "contracts"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "contractguard"
    database_url: str = ""  # Override with full URL if needed

    # MCP Configuration
    mcp_filesystem_enabled: bool = False
    mcp_filesystem_root: str = "/app/data"

    # A2A Configuration
    a2a_enabled: bool = True
    a2a_server_url: str = ""  # Auto-generated if empty

    # Observability
    enable_tracing: bool = True
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "contractguard-ai"

    # Deployment
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    cloud_run_service_name: str = "contractguard-ai"

    # Security
    secret_key: str = "change-this-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def effective_database_url(self) -> str:
        """Get the effective database URL (async)."""
        if self.database_url:
            return self.database_url
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Alias for alembic compatibility
    @property
    def database_url_sync(self) -> str:
        """Get sync database URL for Alembic migrations."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()
