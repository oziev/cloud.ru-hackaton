
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import zipfile
import io
import json
from shared.utils.database import get_db_dependency, Session
from shared.models.database import TestCase, Request
from shared.utils.logger import api_logger
router = APIRouter(prefix="/tests", tags=["Tests"])
class TestCaseResponse(BaseModel):
    test_id: UUID
    test_name: str
    test_type: str
    test_code: Optional[str] = None
    priority: Optional[int] = None
    allure_tags: Optional[List[str]] = None
    validation_status: Optional[str] = None
    created_at: datetime
class TestSearchResponse(BaseModel):
    tests: List[TestCaseResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
@router.get("", response_model=TestSearchResponse)
async def search_tests(
    search: Optional[str] = Query(None, description="Поиск по названию или коду теста"),
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу валидации"),
    test_type: Optional[str] = Query(None, description="Фильтр по типу теста (manual/automated)"),
    request_id: Optional[UUID] = Query(None, description="Фильтр по request_id"),
    priority: Optional[int] = Query(None, description="Фильтр по приоритету"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(20, ge=1, le=100, description="Количество на странице"),
    db: Session = Depends(get_db_dependency)
):
    try:
        query = db.query(TestCase)
        if search:
            query = query.filter(
                (TestCase.test_name.ilike(f"%{search}%")) |
                (TestCase.test_code.ilike(f"%{search}%"))
            )
        if status_filter:
            query = query.filter(TestCase.validation_status == status_filter)
        if test_type:
            query = query.filter(TestCase.test_type == test_type)
        if request_id:
            query = query.filter(TestCase.request_id == request_id)
        if priority is not None:
            query = query.filter(TestCase.priority == priority)
        total = query.count()
        offset = (page - 1) * per_page
        tests = query.order_by(TestCase.created_at.desc()).offset(offset).limit(per_page).all()
        total_pages = (total + per_page - 1) // per_page
        return TestSearchResponse(
            tests=[
                TestCaseResponse(
                    test_id=test.test_id,
                    test_name=test.test_name,
                    test_type=test.test_type,
                    test_code=test.test_code,
                    priority=test.priority,
                    allure_tags=test.allure_tags,
                    validation_status=test.validation_status,
                    created_at=test.created_at
                )
                for test in tests
            ],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
    except Exception as e:
        api_logger.error(f"Error searching tests: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching tests: {str(e)}"
        )
@router.get("/export")
async def export_tests(
    request_id: Optional[UUID] = Query(None, description="Экспорт тестов для конкретного request"),
    format: str = Query("zip", description="Формат экспорта: zip, json, yaml"),
    include_code: bool = Query(True, description="Включить код тестов"),
    db: Session = Depends(get_db_dependency)
):
    try:
        query = db.query(TestCase)
        if request_id:
            query = query.filter(TestCase.request_id == request_id)
        tests = query.all()
        if not tests:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tests found for export"
            )
        if format == "zip":
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for test in tests:
                    if include_code and test.test_code:
                        zip_file.writestr(
                            f"tests/{test.test_name}.py",
                            test.test_code
                        )
                    metadata = {
                        "test_id": str(test.test_id),
                        "test_name": test.test_name,
                        "test_type": test.test_type,
                        "priority": test.priority,
                        "allure_tags": test.allure_tags
                    }
                    zip_file.writestr(
                        f"metadata/{test.test_name}.json",
                        json.dumps(metadata, indent=2)
                    )
            zip_buffer.seek(0)
            from fastapi.responses import Response
            return Response(
                content=zip_buffer.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=tests_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
                }
            )
        elif format == "json":
            data = [
                {
                    "test_id": str(test.test_id),
                    "test_name": test.test_name,
                    "test_type": test.test_type,
                    "test_code": test.test_code if include_code else None,
                    "priority": test.priority,
                    "allure_tags": test.allure_tags,
                    "validation_status": test.validation_status,
                    "created_at": test.created_at.isoformat()
                }
                for test in tests
            ]
            from fastapi.responses import JSONResponse
            return JSONResponse(
                content=data,
                headers={
                    "Content-Disposition": f"attachment; filename=tests_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                }
            )
        elif format == "yaml":
            import yaml
            data = [
                {
                    "test_id": str(test.test_id),
                    "test_name": test.test_name,
                    "test_type": test.test_type,
                    "test_code": test.test_code if include_code else None,
                    "priority": test.priority,
                    "allure_tags": test.allure_tags,
                    "validation_status": test.validation_status,
                    "created_at": test.created_at.isoformat()
                }
                for test in tests
            ]
            yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
            from fastapi.responses import Response
            return Response(
                content=yaml_content,
                media_type="application/x-yaml",
                headers={
                    "Content-Disposition": f"attachment; filename=tests_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.yaml"
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format: {format}. Supported: zip, json, yaml"
            )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Error exporting tests: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting tests: {str(e)}"
        )