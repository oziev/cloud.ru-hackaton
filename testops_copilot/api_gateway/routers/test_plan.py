
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from shared.utils.database import get_db_dependency, Session
from shared.utils.redis_client import redis_client
from agents.test_plan.test_plan_generator_agent import TestPlanGeneratorAgent
from shared.utils.logger import api_logger
router = APIRouter(prefix="/test-plan", tags=["Test Plan"])
class GenerateTestPlanRequest(BaseModel):
    requirements: List[str] = Field(..., min_items=1, description="Список требований")
    project_key: Optional[str] = Field(None, description="Ключ проекта для анализа дефектов")
    components: Optional[List[str]] = Field(default=None, description="Список компонентов для анализа")
    days_back: Optional[int] = Field(default=90, description="Количество дней для анализа дефектов")
    defect_history: Optional[List[Dict[str, Any]]] = Field(default=None, description="История дефектов для анализа")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Дополнительные параметры")
class GenerateTestPlanResponse(BaseModel):
    request_id: UUID
    test_plan: Dict[str, Any]
    defect_analysis: Optional[Dict[str, Any]] = None
    created_at: datetime
class PrioritizeTestsRequest(BaseModel):
    tests: List[Dict[str, Any]] = Field(..., description="Список тестов для приоритизации")
    project_key: Optional[str] = Field(None, description="Ключ проекта для анализа дефектов")
    components: Optional[List[str]] = Field(default=None, description="Список компонентов")
class PrioritizeTestsResponse(BaseModel):
    prioritized_tests: List[Dict[str, Any]]
    defect_analysis: Optional[Dict[str, Any]] = None
@router.post("/generate", response_model=GenerateTestPlanResponse, status_code=status.HTTP_200_OK)
async def generate_test_plan(
    request: GenerateTestPlanRequest,
    db: Session = Depends(get_db_dependency)
):
    try:
        api_logger.info(
            "Generating test plan",
            extra={
                "requirements_count": len(request.requirements),
                "project_key": request.project_key,
                "components": request.components
            }
        )
        generator = TestPlanGeneratorAgent()
        test_plan = await generator.generate_test_plan(
            requirements=request.requirements,
            project_key=request.project_key,
            components=request.components,
            options={
                "days_back": request.days_back,
                "defect_history": request.defect_history,
                **(request.options or {})
            }
        )
        defect_analysis = None
        if request.project_key:
            try:
                from agents.test_plan.defect_analyzer import DefectAnalyzer
                analyzer = DefectAnalyzer()
                defect_analysis = await analyzer.analyze_defect_history(
                    project_key=request.project_key,
                    days_back=request.days_back,
                    components=request.components
                )
            except Exception as e:
                api_logger.warning(f"Error getting defect analysis: {e}")
        test_plan["metadata"]["generated_at"] = datetime.now().isoformat()
        import uuid
        request_id = uuid.uuid4()
        api_logger.info(
            "Test plan generated successfully",
            extra={
                "request_id": str(request_id),
                "test_cases_count": len(test_plan.get("test_cases", []))
            }
        )
        return GenerateTestPlanResponse(
            request_id=request_id,
            test_plan=test_plan,
            defect_analysis=defect_analysis,
            created_at=datetime.now()
        )
    except Exception as e:
        api_logger.error(f"Error generating test plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating test plan: {str(e)}"
        )
@router.post("/prioritize", response_model=PrioritizeTestsResponse, status_code=status.HTTP_200_OK)
async def prioritize_tests(
    request: PrioritizeTestsRequest,
    db: Session = Depends(get_db_dependency)
):
    try:
        api_logger.info(
            "Prioritizing tests",
            extra={
                "tests_count": len(request.tests),
                "project_key": request.project_key
            }
        )
        generator = TestPlanGeneratorAgent()
        defect_analysis = None
        if request.project_key:
            try:
                from agents.test_plan.defect_analyzer import DefectAnalyzer
                analyzer = DefectAnalyzer()
                defect_analysis = await analyzer.analyze_defect_history(
                    project_key=request.project_key,
                    components=request.components
                )
            except Exception as e:
                api_logger.warning(f"Error getting defect analysis: {e}")
        prioritized_tests = generator.prioritize_tests(
            tests=request.tests,
            defect_analysis=defect_analysis
        )
        api_logger.info(
            "Tests prioritized successfully",
            extra={
                "tests_count": len(prioritized_tests)
            }
        )
        return PrioritizeTestsResponse(
            prioritized_tests=prioritized_tests,
            defect_analysis=defect_analysis
        )
    except Exception as e:
        api_logger.error(f"Error prioritizing tests: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error prioritizing tests: {str(e)}"
        )