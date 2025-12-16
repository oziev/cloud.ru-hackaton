
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from agents.validator.validator_agent import ValidatorAgent
router = APIRouter(prefix="/validate", tags=["Validation"])
class ValidateRequest(BaseModel):
    test_code: str = Field(..., description="Python код тест-кейса")
    validation_level: Literal["syntax", "semantic", "full"] = Field(
        default="full",
        description="Уровень валидации"
    )
    class Config:
        pass
class ValidationError(BaseModel):
    type: str
    line: Optional[int] = None
    message: str
class ValidationResponse(BaseModel):
    valid: bool
    score: int = Field(..., ge=0, le=100, description="Оценка качества 0-100")
    syntax_errors: List[ValidationError] = []
    semantic_errors: List[ValidationError] = []
    logic_errors: List[ValidationError] = []
    safety_issues: List[dict] = []
    warnings: List[str] = []
    recommendations: List[str] = []
@router.post("/tests", response_model=ValidationResponse)
async def validate_tests(
    request: ValidateRequest
):
    validator = ValidatorAgent()
    try:
        result = validator.validate(
            test_code=request.test_code,
            validation_level=request.validation_level
        )
        # Преобразуем ошибки в формат ValidationError, добавляя type если отсутствует
        def normalize_error(error):
            if isinstance(error, dict):
                # Если уже есть type, возвращаем как есть
                if "type" in error:
                    return error
                # Иначе добавляем type на основе других полей
                error_type = error.get("type", "unknown_error")
                if not error_type or error_type == "unknown_error":
                    # Определяем тип на основе сообщения
                    msg = error.get("message", "").lower()
                    if "syntax" in msg or "parse" in msg or "отступ" in msg:
                        error_type = "syntax_error"
                    elif "decorator" in msg:
                        error_type = "missing_decorator"
                    elif "assertion" in msg:
                        error_type = "missing_assertion"
                    else:
                        error_type = "validation_error"
                return {
                    "type": error_type,
                    "line": error.get("line"),
                    "message": error.get("message", str(error))
                }
            return {
                "type": "unknown_error",
                "line": None,
                "message": str(error)
            }
        
        syntax_errors = [normalize_error(e) for e in result.get("syntax_errors", [])]
        semantic_errors = [normalize_error(e) for e in result.get("semantic_errors", [])]
        logic_errors = [normalize_error(e) for e in result.get("logic_errors", [])]
        
        return ValidationResponse(
            valid=result.get("passed", False),
            score=result.get("score", 0),
            syntax_errors=syntax_errors,
            semantic_errors=semantic_errors,
            logic_errors=logic_errors,
            safety_issues=result.get("safety_issues", []),
            warnings=result.get("warnings", []),
            recommendations=result.get("recommendations", [])
        )
    except Exception as e:
        from shared.utils.logger import api_logger
        api_logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error: {str(e)}"
        )