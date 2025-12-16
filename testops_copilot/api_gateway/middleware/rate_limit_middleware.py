
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from typing import Optional, Tuple, Dict
from shared.utils.redis_client import redis_client
from shared.config.settings import settings
from shared.utils.logger import api_logger
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = None, burst: int = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.rate_limit_per_minute
        self.burst = burst or settings.rate_limit_burst
        self.redis = redis_client.cache
        self.tokens_per_second = self.requests_per_minute / 60.0
        self.max_tokens = self.burst
    def _get_client_identifier(self, request: Request) -> str:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key}"
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        # Получаем реальный IP из заголовков прокси (Nginx)
        client_ip = request.headers.get("X-Real-IP")
        if not client_ip:
            client_ip = request.headers.get("X-Forwarded-For")
            if client_ip:
                # X-Forwarded-For может содержать несколько IP через запятую
                client_ip = client_ip.split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    def _get_rate_limit_key(self, identifier: str, path: str) -> str:
        normalized_path = path.split("?")[0]
        return f"rate_limit:{identifier}:{normalized_path}"
    def _token_bucket_check(self, key: str) -> Tuple[bool, Dict]:
        try:
            current_time = time.time()
            bucket_data = self.redis.get(key)
            if bucket_data:
                try:
                    tokens, last_refill_time = map(float, bucket_data.decode().split(":"))
                except:
                    tokens, last_refill_time = 0.0, current_time
            else:
                tokens = self.max_tokens
                last_refill_time = current_time
            time_passed = current_time - last_refill_time
            tokens_to_add = time_passed * self.tokens_per_second
            tokens = min(self.max_tokens, tokens + tokens_to_add)
            if tokens >= 1.0:
                tokens -= 1.0
                allowed = True
            else:
                allowed = False
            bucket_data_str = f"{tokens}:{current_time}"
            try:
                self.redis.setex(key, 120, bucket_data_str)
            except Exception as e:
                api_logger.warning(f"Redis setex error: {e}")
            if not allowed:
                tokens_needed = 1.0 - tokens
                wait_seconds = tokens_needed / self.tokens_per_second
                reset_time = int(current_time + wait_seconds)
            else:
                tokens_to_fill = self.max_tokens - tokens
                wait_seconds = tokens_to_fill / self.tokens_per_second if tokens_to_fill > 0 else 0
                reset_time = int(current_time + wait_seconds)
            info = {
                "limit": self.requests_per_minute,
                "remaining": int(tokens) if allowed else 0,
                "reset": reset_time,
                "retry_after": int(wait_seconds) if not allowed else None
            }
            return allowed, info
        except Exception as e:
            api_logger.warning(f"Redis error in rate limit check: {e}")
            return True, {"limit": self.requests_per_minute, "remaining": 100, "reset": int(time.time()) + 60, "retry_after": None}
    async def dispatch(self, request: Request, call_next):
        # Отключаем rate limiting для критических endpoints
        if request.url.path in ["/health", "/ready", "/metrics", "/docs", "/openapi.json", "/", 
                                "/api/v1/tasks", "/api/v1/generate/test-cases", "/api/v1/generate/api-tests",
                                "/api/v1/stream"] or request.url.path.startswith("/api/v1/tasks/") or request.url.path.startswith("/api/v1/stream/"):
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = "999"
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
            return response
        client_ip = request.client.host if request.client else "unknown"
        if client_ip in ["127.0.0.1", "localhost", "::1"] or "localhost" in str(request.url):
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = "999"
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
            return response
        try:
            client_id = self._get_client_identifier(request)
            rate_limit_key = self._get_rate_limit_key(client_id, str(request.url.path))
            allowed, rate_limit_info = self._token_bucket_check(rate_limit_key)
        except Exception as e:
            api_logger.warning(f"Rate limit check failed, allowing request: {e}", exc_info=True)
            response = await call_next(request)
            return response
        if not allowed:
            api_logger.warning(
                "Rate limit exceeded",
                extra={
                    "client_id": client_id,
                    "path": request.url.path,
                    "limit": rate_limit_info["limit"],
                    "retry_after": rate_limit_info["retry_after"]
                }
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate Limit Exceeded",
                    "message": f"Too many requests. Limit: {rate_limit_info.get('limit', self.requests_per_minute)} requests per minute",
                    "retry_after": rate_limit_info.get("retry_after")
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limit_info.get("limit", self.requests_per_minute)),
                    "X-RateLimit-Remaining": str(rate_limit_info.get("remaining", 0)),
                    "X-RateLimit-Reset": str(rate_limit_info.get("reset", int(time.time()) + 60)),
                    "Retry-After": str(rate_limit_info.get("retry_after", 60)) if rate_limit_info.get("retry_after") else "60"
                }
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_limit_info["reset"])
        return response