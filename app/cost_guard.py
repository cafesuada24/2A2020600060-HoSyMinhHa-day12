"""Cost Guard module."""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import HTTPException

logger = logging.getLogger(__name__)

MODEL_PRICE: dict[str, tuple[float, float]] = {
    'gpt-4o-mini': (15e-5, 6e-4),
    'gpt-4o': (5e-3, 15e-3),
    'gemini-3.1-flash-lite-preview': (0.0, 0.0),
}


def _calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    input_cost = (input_tokens / 1000) * MODEL_PRICE[model][0]
    output_cost = (output_tokens / 1000) * MODEL_PRICE[model][1]
    return round(input_cost + output_cost, 6)


@dataclass
class UsageRecord:
    """User usage record."""

    user_id: str
    total_tokens: dict[str, list[int]] = field(
        default_factory=lambda: defaultdict(lambda: [0, 0]),
    )
    requests_count: int = 0
    day: str = field(default_factory=lambda: time.strftime('%Y-%m-%d'))

    @property
    def total_cost_usd(self) -> float:
        """Return user total usage cost."""
        total_cost = 0.0
        for model, (
            total_input_tokens,
            total_output_tokens,
        ) in self.total_tokens.items():
            total_cost += _calculate_cost(
                total_input_tokens,
                total_output_tokens,
                model,
            )
        return total_cost


class CostGuard:
    """A simple CostGuard."""

    def __init__(
        self,
        daily_budget_usd: float = 1.0,
        global_daily_budget_usd: float = 10.0,
        warn_threshold: float = 0.8,
    ) -> None:
        """Init costguard."""
        self.daily_budget_usd = daily_budget_usd
        self.global_daily_budget_usd = global_daily_budget_usd
        self.warn_threshold = warn_threshold

        self._records: dict[str, UsageRecord] = {}
        self._global_today = time.strftime('%Y-%m-%d')
        self._global_cost = 0.0

    def _get_record(self, user_id: str) -> UsageRecord:
        today = time.strftime('%Y-%m-%d')
        record = self._records.get(user_id)
        if not record or record.day != today:
            self._records[user_id] = UsageRecord(user_id=user_id, day=today)
        return self._records[user_id]

    def check_user_budget(self, user_id: str) -> None:
        """Return HTTPException(402) if exceeded."""
        record = self._get_record(user_id)

        if self._global_cost >= self.global_daily_budget_usd:
            logger.info(f'GLOBAL BUDGE EXCEEDED: ${self._global_cost:.4f}')
            raise HTTPException(
                status_code=503,
                detail='Service temporarily unavailable due to budget limits. Try again tomorrow.',
            )
        if record.total_cost_usd >= self.daily_budget_usd:
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    'error': 'Daily budget exceeded',
                    'used_usd': record.total_cost_usd,
                    'budget_usd': self.daily_budget_usd,
                    'resets_at': 'midnight UTC',
                },
            )

        if record.total_cost_usd >= self.daily_budget_usd * self.warn_threshold:
            logger.warning(
                f'User {user_id} at {record.total_cost_usd / self.daily_budget_usd * 100:.0f}% budget',
            )

    def record_usage(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str = 'gpt-4o-mini',
    ) -> UsageRecord:
        """Record user usage after sucessfully calling LLM."""
        record = self._get_record(user_id)
        record.total_tokens[model][0] = input_tokens
        record.total_tokens[model][1] += output_tokens

        cost = _calculate_cost(input_tokens, output_tokens, model)
        self._global_cost += cost

        logger.info(
            f'Usage: user={user_id} req={record.requests_count} '
            f'cost=${record.total_cost_usd:.4f}/{self.daily_budget_usd}',
        )
        return record
