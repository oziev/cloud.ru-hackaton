
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal
from uuid import UUID
from datetime import datetime
from shared.utils.database import get_db_dependency, Session
from shared.utils.redis_client import redis_client
from workers.celery_app import generate_test_cases_task, generate_api_tests_task
router = APIRouter(prefix="/generate", tags=["Generation"])
class GenerateTestCasesRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL для тестирования")
    requirements: List[str] = Field(..., min_items=1, description="Список требований")
    test_type: Literal["manual", "automated", "both"] = Field(..., description="Тип тестов")
    options: Optional[dict] = Field(default=None, description="Дополнительные параметры")
    use_langgraph: bool = Field(default=True, description="Использовать LangGraph workflow с checkpointing")
class GenerateAPITestsRequest(BaseModel):
    openapi_url: Optional[HttpUrl] = Field(None, description="URL к OpenAPI спецификации")
    openapi_spec: Optional[str] = Field(None, description="YAML содержимое OpenAPI (если файл загружен)")
    endpoints: Optional[List[str]] = Field(default=None, description="Список endpoints для покрытия")
    test_types: Optional[List[str]] = Field(default=["positive"], description="Типы тестов")
    options: Optional[dict] = Field(default=None, description="Параметры генерации")
class GenerateResponse(BaseModel):
    request_id: UUID
    task_id: str
    status: str
    stream_url: str
    created_at: datetime
    endpoints_count: Optional[int] = None
    class Config:
        pass
@router.post("/test-cases", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_test_cases(
    request: GenerateTestCasesRequest,
    db: Session = Depends(get_db_dependency)
):
    from shared.models.database import Request
    import uuid
    request_id = uuid.uuid4()
    try:
        db_request = Request(
            request_id=request_id,
            url=str(request.url),
            requirements=request.requirements,
            test_type=request.test_type,
            status="pending"
        )
        db.add(db_request)
        db.commit()
        db.flush()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create request: {str(e)}"
        )
    if request.use_langgraph:
        try:
            from workers.tasks.langgraph_celery_task import run_langgraph_workflow
            task = run_langgraph_workflow.delay(
                request_id=str(request_id),
                url=str(request.url),
                requirements=request.requirements,
                test_type=request.test_type,
                options=request.options or {},
                use_langgraph=True
            )
        except ImportError:
            task = generate_test_cases_task.delay(
                request_id=str(request_id),
                url=str(request.url),
                requirements=request.requirements,
                test_type=request.test_type,
                options=request.options or {}
            )
    else:
        task = generate_test_cases_task.delay(
            request_id=str(request_id),
            url=str(request.url),
            requirements=request.requirements,
            test_type=request.test_type,
            options=request.options or {}
        )
    try:
        db_request.celery_task_id = task.id
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error updating celery_task_id: {e}")
    return GenerateResponse(
        request_id=request_id,
        task_id=task.id,
        status="pending",
        stream_url=f"/api/v1/stream/{request_id}",
        created_at=datetime.utcnow()
    )
@router.post("/api-tests", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_api_tests(
    request: GenerateAPITestsRequest,
    db: Session = Depends(get_db_dependency)
):
    from shared.models.database import Request
    import uuid
    if not request.openapi_url and not request.openapi_spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="openapi_url or openapi_spec is required"
        )
    request_id = uuid.uuid4()
    try:
        db_request = Request(
            request_id=request_id,
            url=str(request.openapi_url) if request.openapi_url else "uploaded_file",
            requirements=[],
            test_type="api",
            status="pending"
        )
        db.add(db_request)
        db.commit()
        db.flush()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create request: {str(e)}"
        )
    task = generate_api_tests_task.delay(
        request_id=str(request_id),
        openapi_url=str(request.openapi_url) if request.openapi_url else None,
        openapi_spec=request.openapi_spec,
        endpoints=request.endpoints,
        test_types=request.test_types,
        options=request.options or {}
    )
    try:
        db_request.celery_task_id = task.id
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error updating celery_task_id: {e}")
    endpoints_count = len(request.endpoints) if request.endpoints else 25
    return GenerateResponse(
        request_id=request_id,
        task_id=task.id,
        status="pending",
        stream_url=f"/api/v1/stream/{request_id}",
        created_at=datetime.utcnow(),
        endpoints_count=endpoints_count
    )