
from celery import Celery
from shared.config.settings import settings
from shared.utils.tracing import setup_tracing
celery_app = Celery(
    "testops_copilot",
    broker=settings.celery_broker,
    backend=settings.celery_result,
    include=[
        "workers.tasks.generate_workflow",
        "workers.tasks.generate_api_workflow",
        "workers.tasks.langgraph_workflow",
        "workers.tasks.langgraph_celery_task"
    ]
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.celery_task_timeout,
    task_soft_time_limit=settings.celery_task_timeout - 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
try:
    setup_tracing(celery_app=celery_app)
except Exception as e:
    from shared.utils.logger import api_logger
    api_logger.warning(f"Celery tracing setup failed: {e}")
from workers.tasks.generate_workflow import generate_test_cases_task
from workers.tasks.generate_api_workflow import generate_api_tests_task
try:
    from workers.tasks.langgraph_celery_task import run_langgraph_workflow, resume_langgraph_workflow
    LANGGRAPH_TASKS_AVAILABLE = True
except ImportError:
    LANGGRAPH_TASKS_AVAILABLE = False
    run_langgraph_workflow = None
    resume_langgraph_workflow = None
__all__ = ["celery_app", "generate_test_cases_task", "generate_api_tests_task"]
if LANGGRAPH_TASKS_AVAILABLE:
    __all__.extend(["run_langgraph_workflow", "resume_langgraph_workflow"])