
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
from shared.config.settings import settings
from shared.utils.database import init_db
from shared.utils.logger import api_logger
from api_gateway.routers import generate, tasks, validate, optimize, health, stream, test_plan, integrations, tests
from api_gateway.middleware.logging_middleware import LoggingMiddleware
from api_gateway.middleware.rate_limit_middleware import RateLimitMiddleware
from shared.utils.tracing import setup_tracing
from api_gateway.routers import metrics as metrics_router
import logging
@asynccontextmanager
async def lifespan(app: FastAPI):
    api_logger.info("Starting API Gateway", extra={"host": settings.api_gateway_host, "port": settings.api_gateway_port})
    try:
        init_db()
        api_logger.info("Database initialized")
    except Exception as e:
        api_logger.error(f"Database initialization error: {e}", exc_info=True)
    try:
        setup_tracing(app=app)
        api_logger.info("Tracing enabled")
    except Exception as e:
        api_logger.warning(f"Tracing setup failed: {e}")
    yield
    api_logger.info("Shutting down API Gateway...")
app = FastAPI(
    title="TestOps Copilot API",
    description="AI QA Assistant для автоматической генерации тест-кейсов",
    version="1.0.0",
    lifespan=lifespan
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(generate.router, prefix="/api/v1", tags=["Generation"])
app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])
app.include_router(stream.router, prefix="/api/v1", tags=["Streaming"])
app.include_router(validate.router, prefix="/api/v1", tags=["Validation"])
app.include_router(optimize.router, prefix="/api/v1", tags=["Optimization"])
app.include_router(test_plan.router, prefix="/api/v1", tags=["Test Plan"])
app.include_router(integrations.router, prefix="/api/v1", tags=["Integrations"])
app.include_router(tests.router, prefix="/api/v1", tags=["Tests"])
app.include_router(health.router, tags=["Health"])
app.include_router(metrics_router.router, prefix="/api/v1", tags=["Metrics"])
try:
    import os
    static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")
        @app.get("/")
        async def root():
            from fastapi.responses import FileResponse
            index_path = os.path.join(static_path, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"message": "TestOps Copilot API", "docs": "/docs"}
except Exception as e:
    api_logger.warning(f"Could not mount static files: {e}")

# Обработка favicon.ico для устранения 404 ошибок
@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)  # No Content
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    error_trace = traceback.format_exc()
    api_logger.error(
        f"Global exception: {exc}",
        extra={
            "path": str(request.url),
            "method": request.method,
            "error_type": type(exc).__name__,
            "traceback": error_trace
        },
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "request_id": getattr(request.state, "request_id", None) if hasattr(request, 'state') else None,
            "type": type(exc).__name__
        }
    )
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_gateway_host,
        port=settings.api_gateway_port,
        reload=settings.api_gateway_reload
    )