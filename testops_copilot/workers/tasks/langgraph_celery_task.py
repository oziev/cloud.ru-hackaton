
from celery import Task
from workers.celery_app import celery_app
from workers.tasks.langgraph_workflow import LangGraphWorkflow
from shared.utils.database import get_db
from shared.models.database import Request
import uuid
from datetime import datetime
class LangGraphWorkflowTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        request_id = kwargs.get("request_id") or (args[0] if args else None)
        if request_id:
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = str(exc)
                    db.commit()
@celery_app.task(
    bind=True,
    base=LangGraphWorkflowTask,
    name="workers.tasks.langgraph_celery_task.run_langgraph_workflow"
)
def run_langgraph_workflow(
    self,
    request_id: str,
    url: str,
    requirements: list,
    test_type: str,
    options: dict = None,
    use_langgraph: bool = True
):
    options = options or {}
    try:
        # Извлекаем thread_id до закрытия сессии
        thread_id = None
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            if not request:
                raise ValueError(f"Request {request_id} not found")
            # Извлекаем значения до закрытия сессии
            thread_id = request.langgraph_thread_id
        if use_langgraph:
            workflow = LangGraphWorkflow()
            result = workflow.run_workflow(
                request_id=request_id,
                url=url,
                requirements=requirements,
                test_type=test_type,
                options=options,
                thread_id=thread_id
            )
            return result
        else:
            from workers.tasks.generate_workflow import generate_test_cases_task
            return generate_test_cases_task(
                request_id=request_id,
                url=url,
                requirements=requirements,
                test_type=test_type,
                options=options
            )
    except Exception as e:
        error_msg = str(e)
        print(f"Error in run_langgraph_workflow: {error_msg}")
        import traceback
        traceback.print_exc()
        try:
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = error_msg
                    request.completed_at = datetime.utcnow()
                    db.commit()
        except Exception as db_error:
            print(f"Error updating request status: {db_error}")
        raise
@celery_app.task(
    bind=True,
    base=LangGraphWorkflowTask,
    name="workers.tasks.langgraph_celery_task.resume_langgraph_workflow"
)
def resume_langgraph_workflow(self, request_id: str):
    try:
        workflow = LangGraphWorkflow()
        result = workflow.resume_workflow(request_id)
        return result
    except Exception as e:
        error_msg = str(e)
        print(f"Error in resume_langgraph_workflow: {error_msg}")
        import traceback
        traceback.print_exc()
        try:
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = error_msg
                    db.commit()
        except Exception as db_error:
            print(f"Error updating request status: {db_error}")
        raise