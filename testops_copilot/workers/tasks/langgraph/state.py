
from typing import TypedDict, Optional, List, Dict, Any
class WorkflowState(TypedDict, total=False):
    request_id: str
    url: str
    requirements: list
    test_type: str
    options: dict
    page_structure: Optional[dict]
    generated_tests: list
    validated_tests: list
    optimized_tests: list
    current_step: str
    error: Optional[str]
    retry_count: int
    validation_errors: Optional[List[Dict[str, Any]]]