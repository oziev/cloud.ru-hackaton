
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram, Gauge
import time
router = APIRouter(prefix="/metrics", tags=["Metrics"])
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM requests',
    ['model', 'status']
)
llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['model', 'type']
)
test_generation_total = Counter(
    'test_generation_total',
    'Total test generations',
    ['type', 'status']
)
active_tasks = Gauge(
    'active_tasks',
    'Number of active tasks',
    ['status']
)
@router.get("")
async def get_metrics():
    return generate_latest(), {"Content-Type": CONTENT_TYPE_LATEST}