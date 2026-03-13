"""Test MinIO configuration validation at startup."""

import pytest
from pydantic_core import ValidationError


def test_rejects_placeholder_minio_access_key():
    """Test that placeholder MinIO access key is rejected."""
    import os
    from src.config import Settings

    original_access = os.environ.get("MINIO_ACCESS_KEY")

    try:
        os.environ["MINIO_ACCESS_KEY"] = "your-minio-access-key"

        with pytest.raises(ValidationError, match="Placeholder value detected"):
            Settings()

    finally:
        if original_access is not None:
            os.environ["MINIO_ACCESS_KEY"] = original_access
        else:
            os.environ.pop("MINIO_ACCESS_KEY", None)


def test_rejects_placeholder_minio_secret_key():
    """Test that placeholder MinIO secret key is rejected."""
    import os
    from src.config import Settings

    original_secret = os.environ.get("MINIO_SECRET_KEY")

    try:
        os.environ["MINIO_SECRET_KEY"] = "your-minio-secret-key"

        with pytest.raises(ValidationError, match="Placeholder value detected"):
            Settings()

    finally:
        if original_secret is not None:
            os.environ["MINIO_SECRET_KEY"] = original_secret
        else:
            os.environ.pop("MINIO_SECRET_KEY", None)


def test_accepts_valid_minio_credentials():
    """Test that valid MinIO credentials are accepted."""
    import os
    from src.config import Settings

    original_access = os.environ.get("MINIO_ACCESS_KEY")
    original_secret = os.environ.get("MINIO_SECRET_KEY")

    try:
        os.environ["MINIO_ACCESS_KEY"] = "valid-access-key-123"
        os.environ["MINIO_SECRET_KEY"] = "valid-secret-key-456"

        settings = Settings()

        assert settings.minio_access_key == "valid-access-key-123"
        assert settings.minio_secret_key == "valid-secret-key-456"

    finally:
        if original_access is not None:
            os.environ["MINIO_ACCESS_KEY"] = original_access
        else:
            os.environ.pop("MINIO_ACCESS_KEY", None)

        if original_secret is not None:
            os.environ["MINIO_SECRET_KEY"] = original_secret
        else:
            os.environ.pop("MINIO_SECRET_KEY", None)
