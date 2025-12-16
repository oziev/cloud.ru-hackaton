
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from shared.utils.logger import api_logger
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        api_logger.info(
            "Incoming request",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "query": str(request.url.query),
                "client": request.client.host if request.client else None
            }
        )
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            api_logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "process_time": f"{process_time:.3f}s"
                }
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            api_logger.error(
                f"Request failed: {e}",
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "process_time": f"{process_time:.3f}s"
                },
                exc_info=True
            )
            raise