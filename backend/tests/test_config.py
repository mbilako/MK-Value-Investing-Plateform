import pytest
from pydantic import ValidationError

from mkvip.core.config import Settings


@pytest.mark.parametrize(
    "field",
    [
        "session_duration_days",
        "login_max_attempts",
        "login_lock_minutes",
        "login_ip_max_per_window",
        "login_account_max_per_window",
        "login_rate_limit_window_minutes",
        "mfa_challenge_ttl_minutes",
        "mfa_pending_setup_ttl_minutes",
        "mfa_recovery_code_count",
        "ai_daily_quota",
        "ai_cache_ttl_seconds",
        "yahoo_max_concurrency",
        "yahoo_response_timeout_seconds",
        "yahoo_import_timeout_seconds",
        "yahoo_imports_per_user",
        "smtp_port",
        "smtp_timeout_seconds",
        "email_verification_ttl_hours",
        "password_reset_ttl_minutes",
        "auth_email_cooldown_seconds",
        "auth_email_max_per_hour",
    ],
)
@pytest.mark.parametrize("invalid_value", [0, -1])
def test_security_limits_and_timeouts_require_positive_values(
    field: str,
    invalid_value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: invalid_value})


def test_mfa_encryption_key_must_be_a_valid_fernet_key() -> None:
    with pytest.raises(ValidationError, match="URL-safe base64 Fernet key"):
        Settings(_env_file=None, mfa_encryption_key="not-a-fernet-key")
