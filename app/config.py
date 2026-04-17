"""Production config — 12-Factor: tất cả từ environment variables."""

import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Self

try:
    from dotenv import load_dotenv

    load_dotenv('./.env.local')
except ImportError:
    pass



@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv('HOST', '0.0.0.0'))
    port: int = field(default_factory=lambda: int(os.getenv('PORT', '8000')))
    environment: str = field(
        default_factory=lambda: os.getenv('ENVIRONMENT', 'development'),
    )
    debug: bool = field(
        default_factory=lambda: os.getenv('DEBUG', 'false').lower() == 'true',
    )

    # App
    app_name: str = field(
        default_factory=lambda: os.getenv('APP_NAME', 'Production AI Agent'),
    )
    app_version: str = field(default_factory=lambda: os.getenv('APP_VERSION', '1.0.0'))
    instance_id: str = field(default_factory=lambda: os.getenv('RAILWAY_REPLICA_ID', 'local-instance'))

    # LLM
    openai_api_key: str = field(default_factory=lambda: os.getenv('OPENAI_API_KEY', ''))
    openai_base_url: str = field(default_factory=lambda: os.getenv('OPENAI_BASE_URL', ''))
    llm_model: str = field(
        default_factory=lambda: os.getenv('LLM_MODEL', 'gpt-4o-mini'),
    )

    # Security
    jwt_secret: str = field(
        default_factory=lambda: os.getenv('JWT_SECRET', 'dev-jwt-secret'),
    )
    allowed_origins: list = field(
        default_factory=lambda: os.getenv('ALLOWED_ORIGINS', '*').split(','),
    )

    # Rate limiting
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv('RATE_LIMIT_PER_MINUTE', '20')),
    )

    # Budget
    daily_budget_usd: float = field(
        default_factory=lambda: float(os.getenv('DAILY_BUDGET_USD', '5.0')),
    )

    instance_id: str = field(
        default_factory=lambda: os.getenv('INSTANCE_ID', f'instance-{uuid.uuid4().hex[:6]}'),
    )

    # Storage
    redis_url: str = field(default_factory=lambda: os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

    def validate(self) -> Self:
        """Verify config."""
        logger = logging.getLogger(__name__)
        if self.environment == 'production':
            if self.openai_api_key == 'dev-key-change-me':
                raise ValueError('OPEN_API_KEY must be set in production!')
            if self.jwt_secret == 'dev-jwt-secret':
                raise ValueError('JWT_SECRET must be set in production!')
        if not self.openai_api_key:
            logger.warning('OPENAI_API_KEY not set — using mock LLM')
        return self


settings = Settings().validate()
print(f'REDIS: {settings.redis_url}')
