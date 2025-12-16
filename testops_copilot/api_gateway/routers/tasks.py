
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from shared.utils.database import get_db_dependency, Session
from shared.models.database import Request, TestCase, GenerationMetric
router = APIRouter(prefix="/tasks", tags=["Tasks"])
class TaskStatusResponse(BaseModel):
    request_id: UUID
    status: str
    current_step: Optional[str] = None
    progress: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    result_summary: Optional[dict] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    tests: Optional[List[dict]] = None
    metrics: Optional[List[dict]] = None
@router.get("", response_model=List[TaskStatusResponse])
async def list_tasks(
    limit: int = Query(20, ge=1, le=100, description="Количество задач"),
    offset: int = Query(0, ge=0, description="Смещение"),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    db: Session = Depends(get_db_dependency)
):
    try:
        query = db.query(Request)
        if status:
            query = query.filter(Request.status == status)
        requests = query.order_by(Request.created_at.desc()).offset(offset).limit(limit).all()
        result = []
        for req in requests:
            try:
                # Загружаем все атрибуты пока сессия активна, чтобы избежать ошибки "not bound to a Session"
                # Если объект был изменен в другой транзакции, делаем refresh
                try:
                    db.refresh(req)
                except Exception:
                    # Если refresh не удался (объект отсоединен), просто используем текущие значения
                    pass
                
                # Сохраняем значения атрибутов в переменные для безопасной сериализации
                result_summary = req.result_summary if req.result_summary else {}
                error_message = req.error_message
                retry_count = req.retry_count or 0
                
                result.append(TaskStatusResponse(
                    request_id=req.request_id,
                    status=req.status,
                    current_step=None,
                    progress=None,
                    started_at=req.started_at,
                    completed_at=req.completed_at,
                    estimated_completion=None,
                    result_summary=result_summary,
                    error_message=error_message,
                    retry_count=retry_count,
                    tests=None,
                    metrics=None
                ))
            except Exception as e:
                from shared.utils.logger import api_logger
                api_logger.error(f"Error serializing request {req.request_id}: {e}", exc_info=True)
                continue
        return result
    except Exception as e:
        from shared.utils.logger import api_logger
        api_logger.error(f"Error in list_tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching tasks: {str(e)}"
        )
@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: UUID,
    include_tests: bool = Query(False, description="Включить сгенерированные тесты"),
    include_metrics: bool = Query(False, description="Включить метрики выполнения"),
    db: Session = Depends(get_db_dependency)
):
    request = db.query(Request).filter(Request.request_id == task_id).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    response_data = {
        "request_id": request.request_id,
        "status": request.status,
        "started_at": request.started_at,
        "completed_at": request.completed_at,
        "retry_count": request.retry_count
    }
    if request.status in ["processing", "started", "reconnaissance", "generation", "validation", "optimization"]:
        if request.langgraph_thread_id:
            try:
                from workers.tasks.langgraph_workflow import LangGraphWorkflow
                workflow = LangGraphWorkflow()
                config = {"configurable": {"thread_id": request.langgraph_thread_id}}
                # Используем checkpointer напрямую для получения состояния
                if hasattr(workflow, 'checkpointer') and workflow.checkpointer:
                    try:
                        # Пытаемся получить состояние через checkpointer
                        if hasattr(workflow.checkpointer, 'get'):
                            state = workflow.checkpointer.get(config)
                            if state and hasattr(state, 'values') and state.values:
                                response_data["current_step"] = state.values.get("current_step", request.status)
                            elif state and isinstance(state, dict):
                                response_data["current_step"] = state.get("current_step", request.status)
                        elif hasattr(workflow.app, 'get_state'):
                            # Fallback на старый API, если доступен
                            state = workflow.app.get_state(config)
                            if state and state.values:
                                response_data["current_step"] = state.values.get("current_step", request.status)
                            else:
                                response_data["current_step"] = request.status
                        else:
                            response_data["current_step"] = request.status
                    except Exception as e:
                        from shared.utils.logger import api_logger
                        api_logger.warning(f"Could not get workflow state: {e}")
                        response_data["current_step"] = request.status
                else:
                    response_data["current_step"] = request.status
            except Exception as e:
                from shared.utils.logger import api_logger
                api_logger.warning(f"Error getting workflow state: {e}")
                response_data["current_step"] = request.status
        else:
            response_data["current_step"] = request.status
        step_progress = {
            "started": 10,
            "reconnaissance": 20,
            "generation": 50,
            "validation": 75,
            "optimization": 90
        }
        response_data["progress"] = step_progress.get(request.status, 50)
        if request.started_at:
            from datetime import timedelta
            response_data["estimated_completion"] = request.started_at + timedelta(minutes=2)
    # Возвращаем result_summary если он есть, независимо от статуса
    if request.result_summary:
        response_data["result_summary"] = request.result_summary
    
    # Возвращаем тесты если запрошено, независимо от статуса
    if include_tests:
        try:
            tests = db.query(TestCase).filter(TestCase.request_id == task_id).all()
            response_data["tests"] = [
            {
                "test_id": str(test.test_id),
                "test_name": test.test_name,
                "test_type": test.test_type,
                "test_code": test.test_code,
                "priority": test.priority,
                "allure_tags": test.allure_tags,
                "validation_status": test.validation_status,
                "created_at": test.created_at.isoformat() if test.created_at else None
            }
            for test in tests
        ]
        except Exception as e:
            from shared.utils.logger import api_logger
            api_logger.error(f"Error fetching tests for task {task_id}: {e}", exc_info=True)
            response_data["tests"] = []
    
    # Возвращаем метрики если запрошено, независимо от статуса
    if include_metrics:
        metrics = db.query(GenerationMetric).filter(GenerationMetric.request_id == task_id).all()
        response_data["metrics"] = [
            {
                "agent_name": metric.agent_name,
                "duration_ms": metric.duration_ms,
                "status": metric.status,
                "llm_tokens_total": metric.llm_tokens_total
            }
            for metric in metrics
        ]
    
    if request.status == "failed":
        response_data["error_message"] = request.error_message
    return TaskStatusResponse(**response_data)
@router.post("/{task_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_task(
    task_id: UUID,
    db: Session = Depends(get_db_dependency)
):
    request = db.query(Request).filter(Request.request_id == task_id).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    if not request.langgraph_thread_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task does not use LangGraph workflow. Cannot resume."
        )
    if request.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task is already completed. Cannot resume."
        )
    try:
        from workers.tasks.langgraph_celery_task import resume_langgraph_workflow
        task = resume_langgraph_workflow.delay(str(task_id))
        request.celery_task_id = task.id
        request.status = "started"
        db.commit()
        return {
            "request_id": task_id,
            "task_id": task.id,
            "status": "resuming",
            "message": "Task resume initiated"
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LangGraph is not available. Cannot resume task."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resuming task: {str(e)}"
        )