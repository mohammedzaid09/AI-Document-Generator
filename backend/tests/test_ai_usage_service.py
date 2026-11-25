
import pytest

from app.models.ai_usage import AIUsage
from app.services.ai_usage_service import AIUsageService


def test_reserve_request(db_session, test_user, test_repository):
    service = AIUsageService(db_session)

    usage = service.reserve_request(
        user_id=test_user.id,
        repository_id=test_repository.id,
        estimated_input_tokens=1000,
    )

    assert usage.id is not None
    assert usage.status == "reserved"
    assert usage.estimated_input_tokens == 1000
    assert usage.reserved_output_tokens > 0


def test_complete_request(db_session, test_user, test_repository):
    service = AIUsageService(db_session)

    usage = service.reserve_request(
        test_user.id,
        test_repository.id,
        1000,
    )

    completed = service.complete_request(
        usage_id=usage.id,
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
    )

    assert completed.status == "completed"
    assert completed.input_tokens == 1000
    assert completed.output_tokens == 500
    assert completed.total_tokens == 1500
    assert completed.completed_at is not None


def test_fail_and_release_reservation(
    db_session, test_user, test_repository
):
    service = AIUsageService(db_session)

    usage = service.reserve_request(
        test_user.id,
        test_repository.id,
        1000,
    )

    failed = service.fail_request(usage.id)

    assert failed.status == "failed"

    released = service.release_failed_reservation(usage.id)

    assert released.status == "cancelled"
    assert released.estimated_input_tokens == 0
    assert released.reserved_output_tokens == 0


def test_reject_invalid_input_token_estimate(
    db_session, test_user, test_repository
):
    service = AIUsageService(db_session)

    with pytest.raises(ValueError, match="must be positive"):
        service.reserve_request(
            test_user.id,
            test_repository.id,
            0,
        )


def test_reject_inconsistent_token_counts(
    db_session, test_user, test_repository
):
    service = AIUsageService(db_session)

    usage = service.reserve_request(
        test_user.id,
        test_repository.id,
        1000,
    )

    with pytest.raises(ValueError, match="does not match"):
        service.complete_request(
            usage_id=usage.id,
            input_tokens=1000,
            output_tokens=500,
            total_tokens=2000,
        )


def test_reject_request_after_daily_request_limit(
    db_session, test_user, test_repository, monkeypatch
):
    monkeypatch.setattr(
        "app.services.ai_usage_service.AI_DAILY_REQUEST_LIMIT",
        1,
    )

    service = AIUsageService(db_session)

    service.reserve_request(
        test_user.id,
        test_repository.id,
        1000,
    )

    with pytest.raises(ValueError, match="Daily AI request limit reached"):
        service.reserve_request(
            test_user.id,
            test_repository.id,
            1000,
        )
