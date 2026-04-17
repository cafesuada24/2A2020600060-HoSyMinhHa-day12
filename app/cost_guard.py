import logging
import time
from fastapi import HTTPException

logger = logging.getLogger(__name__)

MODEL_PRICE: dict[str, tuple[float, float]] = {
    'gpt-4o-mini': (15e-5, 6e-4),
    'gpt-4o': (5e-3, 15e-3),
    'gemini-3.1-flash-lite-preview': (0.0, 0.0),
}

def _calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    input_cost = (input_tokens / 1000) * MODEL_PRICE.get(model, (0, 0))[0]
    output_cost = (output_tokens / 1000) * MODEL_PRICE.get(model, (0, 0))[1]
    return round(input_cost + output_cost, 6)

class CostGuard:
    """Cost Guard supporting both in-memory and Redis."""

    def __init__(
        self,
        daily_budget_usd: float = 1.0,
        global_daily_budget_usd: float = 10.0,
        redis_client=None,
    ) -> None:
        self.daily_budget_usd = daily_budget_usd
        self.global_daily_budget_usd = global_daily_budget_usd
        self.redis = redis_client
        
        # Fallback for in-memory
        if not self.redis:
            self._user_costs = {}
            self._global_cost = 0.0
            self._today = time.strftime('%Y-%m-%d')

    def _get_keys(self, user_id: str):
        today = time.strftime('%Y-%m-%d')
        return f"cost:user:{user_id}:{today}", f"cost:global:{today}"

    def check_user_budget(self, user_id: str) -> None:
        if self.redis:
            user_key, global_key = self._get_keys(user_id)
            user_cost = float(self.redis.get(user_key) or 0)
            global_cost = float(self.redis.get(global_key) or 0)
        else:
            today = time.strftime('%Y-%m-%d')
            if self._today != today:
                self._user_costs = {}
                self._global_cost = 0.0
                self._today = today
            user_cost = self._user_costs.get(user_id, 0.0)
            global_cost = self._global_cost

        if global_cost >= self.global_daily_budget_usd:
            raise HTTPException(status_code=503, detail="Global budget exceeded")
        if user_cost >= self.daily_budget_usd:
            raise HTTPException(status_code=402, detail="User budget exceeded")

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int, model: str) -> float:
        cost = _calculate_cost(input_tokens, output_tokens, model)
        
        if self.redis:
            user_key, global_key = self._get_keys(user_id)
            self.redis.incrbyfloat(user_key, cost)
            self.redis.incrbyfloat(global_key, cost)
            self.redis.expire(user_key, 86400 * 2)
            self.redis.expire(global_key, 86400 * 2)
        else:
            self._user_costs[user_id] = self._user_costs.get(user_id, 0.0) + cost
            self._global_cost += cost
            
        return cost

    def get_user_cost(self, user_id: str) -> float:
        if self.redis:
            user_key, _ = self._get_keys(user_id)
            return float(self.redis.get(user_key) or 0)
        return self._user_costs.get(user_id, 0.0)

    def get_global_cost(self) -> float:
        if self.redis:
            _, global_key = self._get_keys("any") # global key doesn't depend on user_id
            return float(self.redis.get(global_key) or 0)
        return self._global_cost
