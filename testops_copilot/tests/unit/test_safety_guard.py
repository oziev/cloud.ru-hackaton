
import pytest
from agents.validator.safety_guard import SafetyGuard
class TestSafetyGuard:
    def test_init(self):
        guard = SafetyGuard()
        assert guard is not None
        assert len(guard.CRITICAL_BLACKLIST) > 0
        assert len(guard.ALLOWED_IMPORTS) > 0
    def test_static_analysis_safe_code(self):
        guard = SafetyGuard()
        safe_code = "def test_example(): assert True"
        result = guard._static_analysis(safe_code)
        assert result["blocked"] == []
    def test_static_analysis_dangerous_code(self):
        guard = SafetyGuard()
        dangerous_code = "__import__('os').system('rm -rf /')"
        result = guard._static_analysis(dangerous_code)
        assert len(result["blocked"]) > 0
    def test_ast_analysis_allowed_imports(self):
        guard = SafetyGuard()
        code = "import pytest\nfrom allure import step"
        result = guard._ast_analysis(code)
        assert len(result["blocked"]) == 0
    def test_ast_analysis_forbidden_imports(self):
        guard = SafetyGuard()
        code = "import os\nos.system('rm -rf /')"
        result = guard._ast_analysis(code)
        assert len(result["blocked"]) > 0
    def test_validate_safe_code(self):
        guard = SafetyGuard()
        safe_code = "def test_example(): assert True"
        result = guard.validate(safe_code)
        assert result["risk_level"] in ["SAFE", "LOW"]
        assert result["action_taken"] == "allowed"
    def test_validate_dangerous_code(self):
        guard = SafetyGuard()
        dangerous_code = "__import__('os').system('rm -rf /')"
        result = guard.validate(dangerous_code)
        assert result["risk_level"] in ["HIGH", "CRITICAL"]
        assert result["action_taken"] == "blocked"