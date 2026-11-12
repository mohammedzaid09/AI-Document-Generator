from datetime import datetime, timezone

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.core.config import (
    AI_DAILY_REQUEST_LIMIT,
    AI_DAILY_TOKEN_LIMIT,
    AI_MAX_INPUT_TOKENS,
    AI_MAX_OUTPUT_TOKENS,
)
from app.models.ai_usage import AIUsage

class AIUsageService:
    # A fixed PostgreSQL advisory-lock key for the global AI budget.
    GLOBAL_BUDGET_LOCK_KEY = 834721

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _get_today():
        return datetime.now(timezone.utc).date()

    def _get_daily_usage(self):
        today = self._get_today()

        actual_tokens = case(
            (AIUsage.status == "completed", AIUsage.total_tokens),
            else_=0,
        )

        reserved_tokens = case(
            (
                AIUsage.status.in_(["reserved", "failed"]),
                AIUsage.estimated_input_tokens
                + AIUsage.reserved_output_tokens,
            ),
            else_=0,
        )

        statement = select(
            func.count(AIUsage.id),
            func.coalesce(func.sum(actual_tokens), 0),
            func.coalesce(func.sum(reserved_tokens), 0),
        ).where(
            AIUsage.request_date == today,
            AIUsage.status.in_(["reserved", "completed", "failed"]),
        )

        return self.db.execute(statement).one()

    def _check_budget(self, estimated_input_tokens: int):
        if estimated_input_tokens <= 0:
            raise ValueError("Input token estimate must be positive.")

        if estimated_input_tokens > AI_MAX_INPUT_TOKENS:
            raise ValueError("Input exceeds the maximum allowed tokens.")

        if AI_MAX_OUTPUT_TOKENS <= 0:
            raise ValueError("Output token limit must be positive.")

        request_count, actual_tokens, reserved_tokens = (
            self._get_daily_usage()
        )

        if request_count >= AI_DAILY_REQUEST_LIMIT:
            raise ValueError("Daily AI request limit reached.")

        projected_tokens = (
            actual_tokens
            + reserved_tokens
            + estimated_input_tokens
            + AI_MAX_OUTPUT_TOKENS
        )

        if projected_tokens > AI_DAILY_TOKEN_LIMIT:
            raise ValueError("Daily AI token limit reached.")

        return True

    def reserve_request(
        self,
        user_id: int,
        repository_id: int,
        estimated_input_tokens: int,
    ):
        try:
            # Lock the global budget while checking and reserving.
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": self.GLOBAL_BUDGET_LOCK_KEY},
            )

            self._check_budget(estimated_input_tokens)

            usage = AIUsage(
                user_id=user_id,
                repository_id=repository_id,
                model_name="gemini",
                request_date=self._get_today(),
                status="reserved",
                estimated_input_tokens=estimated_input_tokens,
                reserved_output_tokens=AI_MAX_OUTPUT_TOKENS,
            )

            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)

            return usage

        except Exception:
            self.db.rollback()
            raise

    def complete_request(
        self,
        usage_id: int,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ):
        try:
            # Lock the global AI budget.
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": self.GLOBAL_BUDGET_LOCK_KEY},
            )

            # Lock the individual usage record.
            usage = self.db.execute(
                select(AIUsage)
                .where(AIUsage.id == usage_id)
                .with_for_update()
            ).scalar_one_or_none()

            if usage is None:
                raise ValueError("AI usage record not found.")

            if usage.status != "reserved":
                raise ValueError("AI usage record is not reserved.")

            if min(input_tokens, output_tokens, total_tokens) < 0:
                raise ValueError("Token counts cannot be negative.")

            if total_tokens != input_tokens + output_tokens:
                raise ValueError("Total token count does not match.")

            usage.input_tokens = input_tokens
            usage.output_tokens = output_tokens
            usage.total_tokens = total_tokens
            usage.status = "completed"
            usage.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(usage)

            return usage

        except Exception:
            self.db.rollback()
            raise

    def fail_request(self, usage_id: int):
        usage = self.db.execute(
            select(AIUsage)
            .where(AIUsage.id == usage_id)
            .with_for_update()
        ).scalar_one_or_none()

        if usage is None:
            raise ValueError("AI usage record not found.")

        if usage.status != "reserved":
            raise ValueError("AI usage record is not reserved.")

        try:
            usage.status = "failed"
            usage.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(usage)

            return usage

        except Exception:
            self.db.rollback()
            raise

    def cancel_reservation(self, usage_id):
        try:
            # Acquire the global budget lock first.
            # This prevents concurrent reservations from calculating
            # the budget while a cancellation is in progress.
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": self.GLOBAL_BUDGET_LOCK_KEY},
            )

            # Lock the specific AI usage record.
            usage = self.db.execute(
                select(AIUsage)
                .where(AIUsage.id == usage_id)
                .with_for_update()
            ).scalar_one_or_none()

            if usage is None:
                raise ValueError("AI usage record not found.")

            if usage.status != "reserved":
                raise ValueError("AI usage record is not reserved.")

            # Mark the reservation as cancelled.
            usage.status = "cancelled"

            # Release the reserved token budget.
            usage.reserved_output_tokens = 0
            usage.estimated_input_tokens = 0

            self.db.commit()
            self.db.refresh(usage)

            return usage

        except Exception:
            self.db.rollback()
            raise


    def release_failed_reservation(self, usage_id: int):
        """Release a failed reservation when no API request was sent."""
        try:
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": self.GLOBAL_BUDGET_LOCK_KEY},
            )

            usage = self.db.execute(
                select(AIUsage)
                .where(AIUsage.id == usage_id)
                .with_for_update()
            ).scalar_one_or_none()

            if usage is None:
                raise ValueError("AI usage record not found.")

            if usage.status != "failed":
                raise ValueError("AI usage record is not failed.")

            usage.status = "cancelled"
            usage.estimated_input_tokens = 0
            usage.reserved_output_tokens = 0

            self.db.commit()
            self.db.refresh(usage)

            return usage

        except Exception:
            self.db.rollback()
            raise


