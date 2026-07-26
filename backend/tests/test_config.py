import pytest
from pydantic import ValidationError

from mkvip.core.config import Settings


@pytest.mark.parametrize(
    "field",
    [
        "session_duration_days",
        "login_max_attempts",
        "login_lock_minutes",
    ],
)
@pytest.mark.parametrize("invalid_value", [0, -1])
def test_security_duration_and_attempt_settings_require_positive_integers(
    field: str,
    invalid_value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: invalid_value})
