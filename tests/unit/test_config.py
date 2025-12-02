"""
Unit Tests for Configuration

Tests configuration loading and validation.
"""

import os
import pytest
from unittest.mock import patch


class TestSettings:
    """Tests for Settings configuration."""

    def test_default_settings(self):
        """Test default settings values."""
        from src.config import Settings

        settings = Settings(google_api_key="test-key")

        assert settings.app_name == "ContractGuard AI"
        assert settings.app_env == "development"
        assert settings.api_port == 8000
        assert settings.gemini_model == "gemini-2.0-flash-exp"

    def test_database_url_construction(self):
        """Test database URL is correctly constructed."""
        from src.config import Settings

        settings = Settings(
            google_api_key="test-key",
            postgres_host="db.example.com",
            postgres_port=5432,
            postgres_user="myuser",
            postgres_password="mypass",
            postgres_db="mydb",
        )

        expected = "postgresql+asyncpg://myuser:mypass@db.example.com:5432/mydb"
        assert settings.effective_database_url == expected

    def test_database_url_override(self):
        """Test database URL override."""
        from src.config import Settings

        custom_url = "postgresql+asyncpg://custom@host/db"
        settings = Settings(
            google_api_key="test-key",
            database_url=custom_url,
        )

        assert settings.effective_database_url == custom_url

    def test_is_production(self):
        """Test is_production property."""
        from src.config import Settings

        dev_settings = Settings(google_api_key="test-key", app_env="development")
        assert dev_settings.is_production is False

        prod_settings = Settings(google_api_key="test-key", app_env="production")
        assert prod_settings.is_production is True

    def test_sync_database_url(self):
        """Test sync database URL for Alembic."""
        from src.config import Settings

        settings = Settings(
            google_api_key="test-key",
            postgres_host="localhost",
            postgres_port=5432,
            postgres_user="postgres",
            postgres_password="postgres",
            postgres_db="contractguard",
        )

        sync_url = settings.database_url_sync
        assert sync_url.startswith("postgresql://")
        assert "asyncpg" not in sync_url

    def test_settings_from_env(self):
        """Test settings loaded from environment variables."""
        with patch.dict(os.environ, {
            "GOOGLE_API_KEY": "env-api-key",
            "APP_ENV": "staging",
            "API_PORT": "9000",
        }):
            from src.config import Settings
            settings = Settings()

            assert settings.google_api_key == "env-api-key"
            assert settings.app_env == "staging"
            assert settings.api_port == 9000

    def test_get_settings_singleton(self):
        """Test that get_settings returns cached instance."""
        from src.config import get_settings

        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_valid_app_env(self):
        """Test valid app_env values."""
        from src.config import Settings

        for env in ["development", "staging", "production"]:
            settings = Settings(google_api_key="test-key", app_env=env)
            assert settings.app_env == env

    def test_minio_settings(self):
        """Test MinIO configuration."""
        from src.config import Settings

        settings = Settings(
            google_api_key="test-key",
            minio_endpoint="minio.example.com:9000",
            minio_access_key="mykey",
            minio_secret_key="mysecret",
            minio_secure=True,
            minio_bucket="my-bucket",
        )

        assert settings.minio_endpoint == "minio.example.com:9000"
        assert settings.minio_secure is True
        assert settings.minio_bucket == "my-bucket"

    def test_redis_url(self):
        """Test Redis URL configuration."""
        from src.config import Settings

        settings = Settings(
            google_api_key="test-key",
            redis_url="redis://redis.example.com:6379/1",
        )

        assert "redis.example.com" in settings.redis_url

    def test_observability_settings(self):
        """Test observability configuration."""
        from src.config import Settings

        settings = Settings(
            google_api_key="test-key",
            enable_tracing=True,
            otel_exporter_otlp_endpoint="http://collector:4317",
            otel_service_name="my-service",
        )

        assert settings.enable_tracing is True
        assert settings.otel_service_name == "my-service"

    def test_security_settings(self):
        """Test security configuration."""
        from src.config import Settings

        settings = Settings(
            google_api_key="test-key",
            secret_key="my-secret-key-32-chars-minimum!!",
            algorithm="HS256",
            access_token_expire_minutes=60,
        )

        assert settings.secret_key == "my-secret-key-32-chars-minimum!!"
        assert settings.algorithm == "HS256"
        assert settings.access_token_expire_minutes == 60
