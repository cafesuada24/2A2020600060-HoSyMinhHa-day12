"""Production AI Agent.

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ JWT Authentication
  ✅ Rate limiting (Sliding window)
  ✅ Cost guard (User & Global budget)
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
"""

import json
import logging
import signal
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, TypedDict
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from app.auth import authenticate_user, create_token, verify_token
from app.config import settings
from app.cost_guard import CostGuard
from app.rate_limiter import RateLimiter

# Mock LLM
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
MAX_CONVERSATION_TURN = 10
INSTANCE_ID = settings.instance_id
_is_ready = False
_request_count = 0
_error_count = 0


# ─────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────
class Message(TypedDict):
    role: str
    content: str
    timestamp: str


# ─────────────────────────────────────────────────────────
# Components
# ─────────────────────────────────────────────────────────

rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_per_minute,
    window_seconds=60,
)
cost_guard = CostGuard(daily_budget_usd=settings.daily_budget_usd)

USE_REDIS = False
_redis = None
_memory_store: dict[str, dict[str, object]] = {}

if settings.redis_url:
    try:
        import redis
        _redis = redis.from_url(settings.redis_url, socket_timeout=2)
        _redis.ping()
        USE_REDIS = True
        logger.info(f'Connected to Redis at {settings.redis_url}')
    except (ImportError, Exception) as e:
        logger.warning(f'Redis not available ({e}) - using in-memory storage.')
else:
    logger.info('REDIS_URL not set - using in-memory storage.')


# ──────────────────────────────────────────────────────────
# Session Storage (Redis-backed, Stateless-compatible)
# ──────────────────────────────────────────────────────────


def get_session_key(user_id: str, session_id: str) -> str:
    return f'session:{user_id}:{session_id}'


def save_session(
    user_id: str,
    session_id: str,
    data: dict,
    ttl_seconds: int = 3600,
) -> None:
    """Lưu session vào Redis với TTL."""
    session_key = get_session_key(user_id=user_id, session_id=session_id)

    serialized = json.dumps(data)
    if USE_REDIS:
        _redis.setex(session_key, ttl_seconds, serialized)
    else:
        _memory_store[session_key] = data


def load_session(user_id: str, session_id: str) -> dict[str, list[Message]]:
    """Load session từ Redis hoặc Memory."""
    session_key = get_session_key(user_id=user_id, session_id=session_id)
    if USE_REDIS:
        data = _redis.get(session_key)
        return json.loads(data) if data else {}
    return _memory_store.get(session_key, {})


def append_to_history(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
) -> list[Message]:
    """Thêm message vào conversation history."""
    session = load_session(user_id, session_id)
    history = session.get('history', [])
    history.append(
        {
            'role': role,
            'content': content,
            'timestamp': datetime.now(UTC).isoformat(),
        },
    )
    # Giữ tối đa 20 messages (10 turns)
    if len(history) > MAX_CONVERSATION_TURN * 2:
        history = history[-(MAX_CONVERSATION_TURN * 2):]
    session['history'] = history
    save_session(user_id, session_id, session)
    return history


# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App lifespan."""
    global _is_ready
    logger.info(
        json.dumps(
            {
                'event': 'startup',
                'app': settings.app_name,
                'version': settings.app_version,
                'environment': settings.environment,
            },
        ),
    )
    # Simulate initialization
    import asyncio
    await asyncio.sleep(0.1)
    _is_ready = True
    logger.info(json.dumps({'event': 'ready'}))

    yield

    _is_ready = False
    logger.info(json.dumps({'event': 'shutdown'}))


# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url='/docs' if settings.environment != 'production' else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=['GET', 'POST'],
    allow_headers=['Authorization', 'Content-Type', 'X-API-Key'],
)


@app.middleware('http')
async def request_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        if 'server' in response.headers:
            del response.headers['server']
        duration = round((time.time() - start) * 1000, 1)
        logger.info(
            json.dumps(
                {
                    'event': 'request',
                    'method': request.method,
                    'path': request.url.path,
                    'status': response.status_code,
                    'ms': duration,
                },
            ),
        )
        return response
    except Exception as e:
        _error_count += 1
        logger.error(
            json.dumps(
                {
                    'event': 'request_error',
                    'method': request.method,
                    'path': request.url.path,
                    'error': str(e),
                },
            ),
        )
        raise


# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(..., examples=['student'])
    password: str = Field(..., examples=['demo123'])


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description='Your question for the agent',
    )
    model: str = Field(
        'gpt-4o-mini',
        description='Model to use (e.g., gpt-4o-mini, gpt-4o)',
    )


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str


class ChatRequest(BaseModel):
    question: str
    model: str = 'gpt-4o-mini'
    session_id: str | None = None  # None = tạo session mới


class ChatResponse(BaseModel):
    session_id: str
    served_by: str
    storage: str

    question: str
    answer: str
    turn: int
    model: str
    timestamp: float


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────


@app.get('/', tags=['Info'])
def root() -> dict[str, object]:
    return {
        'app': settings.app_name,
        'version': settings.app_version,
        'environment': settings.environment,
        'endpoints': {
            'login': 'POST /login',
            'ask': 'POST /ask (requires Authorization: Bearer <token>)',
            'health': 'GET /health',
            'ready': 'GET /ready',
        },
    }


@app.post('/login', response_model=LoginResponse, tags=['Auth'])
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> LoginResponse:
    """Authenticate user.

    Receives credentials via **Form Data** (securely handled by browsers/tools).
    Default credentials: student / demo123
    """
    user = authenticate_user(form_data.username, form_data.password)
    token = create_token(user['username'], user['role'])
    return LoginResponse(access_token=token)


# === ASK ===
@app.post('/ask', response_model=AskResponse, tags=['Agent'])
async def ask_agent(
    body: AskRequest,
    request: Request,
    user: Annotated[dict, Depends(verify_token)],
) -> AskResponse:
    """Send a question to the AI agent.

    **Authentication:** Include header `Authorization: Bearer <your-token>`
    """
    username = user['username']
    # 1. Rate limit check
    rate_limiter.allow_request(username)

    # 2. Budget check
    cost_guard.check_user_budget(username)

    logger.info(
        json.dumps(
            {
                'event': 'agent_call',
                'user': user['username'],
                'q_len': len(body.question),
                'client': str(request.client.host) if request.client else 'unknown',
                'instance_id': INSTANCE_ID,
            },
        ),
    )

    # 3. LLM Call
    answer = llm_ask(body.question)

    # 4. Record usage (mock tokens: 1 word = 2 tokens)
    input_tokens = len(body.question.split()) * 2
    output_tokens = len(answer.split()) * 2
    cost_guard.record_usage(
        user_id=user['username'],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=settings.llm_model,
    )

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(UTC).isoformat(),
    )


# === CHAT ===


@app.post('/chat', tags=['Chat'])
async def chat(
    body: ChatRequest,
    request: Request,
    user: Annotated[dict, Depends(verify_token)],
) -> ChatResponse:
    username = user['username']

    session_id = body.session_id or str(uuid4())

    # 1. Rate limit check
    rate_limiter.allow_request(username)

    # 2. Budget check
    cost_guard.check_user_budget(username)

    # Add user message to history
    append_to_history(username, session_id, 'user', body.question)

    # 3. LLM Call
    answer = llm_ask(body.question)

    # Add assistant message to history
    history = append_to_history(username, session_id, 'assistant', answer)

    logger.info(
        json.dumps(
            {
                'event': 'agent_call_chat',
                'user': username,
                'session_id': session_id,
                'q_len': len(body.question),
                'client': str(request.client.host) if request.client else 'unknown',
                'instance_id': INSTANCE_ID,
            },
        ),
    )

    # 4. Record usage (mock tokens: 1 word = 2 tokens)
    input_tokens = len(body.question.split()) * 2
    output_tokens = len(answer.split()) * 2
    cost_guard.record_usage(
        user_id=username,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=settings.llm_model,
    )

    return ChatResponse(
        session_id=session_id,
        question=body.question,
        answer=answer,
        turn=len([m for m in history if m['role'] == 'user']),
        served_by=INSTANCE_ID,
        storage='redis' if USE_REDIS else 'in-memory',
        model=body.model,
        timestamp=datetime.now(UTC).timestamp(),
    )


@app.get('/chat/{session_id}/history', tags=['Chat'])
def get_history(
    session_id: str,
    user: Annotated[dict, Depends(verify_token)],
) -> dict[str, object]:
    """Retrieve conversation history from a session_id."""
    session = load_session(user['username'], session_id)
    history = session.get('history', [])
    if not history:
        raise HTTPException(404, f'Session {session_id} not found or expired')
    return {
        'session_id': session_id,
        'messages': history,
        'count': len(history),
    }


@app.delete('/chat/{session_id}', tags=['Chat'])
def delete_session(
    session_id: str,
    user: Annotated[dict, Depends(verify_token)],
) -> dict[str, object]:
    """Xóa session (user logout)."""
    session_key = get_session_key(user['username'], session_id)
    if USE_REDIS:
        _redis.delete(session_key)
    else:
        _memory_store.pop(session_key, None)
    return {'user': user['username'], 'deleted': session_id}


@app.get('/health', tags=['Operations'])
def health() -> dict[str, object]:
    """Liveness probe. Platform restarts container if this fails."""
    redis_ok = False
    if USE_REDIS:
        try:
            _redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False

    status = 'ok' if (not USE_REDIS or redis_ok) else 'degraded'

    checks = {'llm': 'mock' if not settings.openai_api_key else 'openai'}
    return {
        'status': status,
        'version': settings.app_version,
        'environment': settings.environment,
        'uptime_seconds': round(time.time() - START_TIME, 1),
        'total_requests': _request_count,
        'checks': checks,
        'timestamp': datetime.now(UTC).isoformat(),
        'storage': 'redis' if USE_REDIS else 'in-memory',
        'instance_id': INSTANCE_ID,
        'redis_connected': redis_ok if USE_REDIS else 'N/A',
    }


@app.get('/ready', tags=['Operations'])
def ready() -> dict[str, object]:
    """Readiness probe. Load balancer stops routing here if not ready."""
    if USE_REDIS:
        try:
            _redis.ping()
        except Exception as e:
            raise HTTPException(503, 'Redis not available') from e
    if not _is_ready:
        raise HTTPException(503, 'Not ready')
    return {'ready': True, 'instance': INSTANCE_ID}


@app.get('/metrics', tags=['Operations'])
def metrics(user: Annotated[dict, Depends(verify_token)]) -> dict[str, object]:
    """Basic metrics (protected)."""
    record = cost_guard._get_record(user['username'])
    stats = rate_limiter.get_stats(user['username'])

    return {
        'uptime_seconds': round(time.time() - START_TIME, 1),
        'total_requests': _request_count,
        'error_count': _error_count,
        'user_metrics': {
            'username': user['username'],
            'daily_cost_usd': round(record.total_cost_usd, 4),
            'daily_budget_usd': cost_guard.daily_budget_usd,
            'budget_used_pct': round(
                record.total_cost_usd / cost_guard.daily_budget_usd * 100,
                1,
            ),
            'rate_limit_stats': stats,
        },
        'global_metrics': {
            'global_daily_cost_usd': round(cost_guard._global_cost, 4),
            'global_daily_budget_usd': cost_guard.global_daily_budget_usd,
        },
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({'event': 'signal', 'signum': signum}))


signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == '__main__':
    logger.info(f'Starting {settings.app_name} on {settings.host}:{settings.port}')
    uvicorn.run(
        'app.main:app',
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
