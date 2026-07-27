import uuid

import pytest

from mkvip.services.yahoo_imports import (
    YahooImportAdmission,
    YahooImportInProgressError,
    YahooImportLimitError,
)


def test_import_admission_rejects_a_duplicate_company_in_flight() -> None:
    admission = YahooImportAdmission(per_user_limit=2)
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()

    with (
        admission.admit(user_id, company_id),
        pytest.raises(YahooImportInProgressError),
        admission.admit(user_id, company_id),
    ):
        pass


def test_import_admission_limits_each_user_without_blocking_another_user() -> None:
    admission = YahooImportAdmission(per_user_limit=1)
    first_user = uuid.uuid4()
    second_user = uuid.uuid4()

    def exceed_first_user_limit() -> None:
        with (
            pytest.raises(YahooImportLimitError),
            admission.admit(first_user, uuid.uuid4()),
        ):
            pass

    with admission.admit(first_user, uuid.uuid4()):
        exceed_first_user_limit()
        with admission.admit(second_user, uuid.uuid4()):
            pass
