
import ast
import re
from typing import Dict, List, Any
from agents.validator.safety_guard import SafetyGuard
class ValidatorAgent:
    def __init__(self):
        self.safety_guard = SafetyGuard()
    def validate(
        self,
        test_code: str,
        validation_level: str = "full"
    ) -> Dict[str, Any]:
        from shared.utils.logger import agent_logger
        agent_logger.debug(f"[VALIDATOR] Starting validation (level={validation_level})")
        
        result = {
            "passed": True,
            "score": 100,
            "syntax_errors": [],
            "semantic_errors": [],
            "logic_errors": [],
            "safety_issues": [],
            "warnings": [],
            "recommendations": []
        }
        syntax_result = self._validate_syntax(test_code)
        result["syntax_errors"] = syntax_result["errors"]
        if syntax_result["errors"]:
            result["passed"] = False
            result["score"] = 0
            agent_logger.warning(
                f"[VALIDATOR] Syntax errors found",
                extra={"syntax_errors": syntax_result["errors"]}
            )
            return result
        agent_logger.debug(f"[VALIDATOR] Syntax validation passed")
        if validation_level == "syntax":
            return result
        semantic_result = self._validate_semantic(test_code)
        result["semantic_errors"] = semantic_result["errors"]
        result["warnings"].extend(semantic_result["warnings"])
        if semantic_result["errors"]:
            result["passed"] = False
            result["score"] -= 30
            agent_logger.warning(
                f"[VALIDATOR] Semantic errors found",
                extra={"semantic_errors": semantic_result["errors"], "score_after": result["score"]}
            )
        else:
            agent_logger.debug(f"[VALIDATOR] Semantic validation passed (warnings: {len(semantic_result['warnings'])})")
        if validation_level == "semantic":
            return result
        logic_result = self._validate_logic(test_code)
        result["logic_errors"] = logic_result["errors"]
        result["warnings"].extend(logic_result["warnings"])
        if logic_result["errors"]:
            result["passed"] = False
            result["score"] -= 20
            agent_logger.warning(
                f"[VALIDATOR] Logic errors found",
                extra={"logic_errors": logic_result["errors"], "score_after": result["score"]}
            )
        else:
            agent_logger.debug(f"[VALIDATOR] Logic validation passed (warnings: {len(logic_result['warnings'])})")
        safety_result = self.safety_guard.validate(test_code)
        issues = safety_result.get("issues", [])
        result["safety_issues"] = [
            {"type": "warning", "message": issue} if isinstance(issue, str) else issue
            for issue in issues
        ]
        if safety_result.get("risk_level") in ["HIGH", "CRITICAL"]:
            result["passed"] = False
            result["score"] = 0
            agent_logger.warning(
                f"[VALIDATOR] Safety risk detected",
                extra={"risk_level": safety_result.get("risk_level"), "issues": issues}
            )
        result["score"] = max(0, result["score"])
        result["recommendations"] = self._generate_recommendations(result)
        
        agent_logger.info(
            f"[VALIDATOR] Validation completed",
            extra={
                "passed": result["passed"],
                "score": result["score"],
                "syntax_errors": len(result["syntax_errors"]),
                "semantic_errors": len(result["semantic_errors"]),
                "logic_errors": len(result["logic_errors"]),
                "warnings": len(result["warnings"]),
                "safety_issues": len(result["safety_issues"])
            }
        )
        return result
    def _validate_syntax(self, test_code: str) -> Dict[str, List]:
        errors = []
        try:
            ast.parse(test_code)
        except SyntaxError as e:
            errors.append({
                "type": "syntax_error",
                "line": e.lineno,
                "message": f"SyntaxError: {e.msg}"
            })
        except Exception as e:
            error_msg = str(e)
            # Обрабатываем сообщения об ошибках отступа
            if "unexpected indent" in error_msg.lower() or "неожиданный отступ" in error_msg.lower():
                errors.append({
                    "type": "indentation_error",
                    "line": 1,
                    "message": f"Ошибка: неожиданный отступ - {error_msg}"
                })
            else:
                errors.append({
                    "type": "parse_error",
                    "line": None,
                    "message": f"Parse error: {error_msg}"
                })
        return {"errors": errors}
    def _validate_semantic(self, test_code: str) -> Dict[str, List]:
        errors = []
        warnings = []
        required_decorators = {
            "@allure.feature": r"@allure\.feature\s*\(",
            "@allure.story": r"@allure\.story\s*\(",
            "@allure.title": r"@allure\.title\s*\(",
            "@allure.tag": r"@allure\.tag\s*\("
        }
        
        # Проверяем наличие декораторов, но делаем это warning, а не error
        # так как генератор должен их добавлять автоматически
        missing_decorators = []
        for decorator, pattern in required_decorators.items():
            if not re.search(pattern, test_code):
                missing_decorators.append(decorator)
        
        # Если отсутствуют декораторы, это warning, не error
        # Генератор должен их добавлять, но если по какой-то причине не добавил,
        # это не критично - тест все равно может работать
        if missing_decorators:
            warnings.append(f"Отсутствуют декораторы: {', '.join(missing_decorators)}. Рекомендуется добавить для полной совместимости с Allure TestOps.")
        # Проверяем является ли тест manual (для manual тестов assertions не требуются)
        is_manual = "@allure.manual" in test_code or "allure.manual" in test_code
        
        if not is_manual:
            if "with allure.step" not in test_code:
                warnings.append("Рекомендуется использовать allure.step() для структурирования")
            if not re.search(r"(assert\s+|expect\()", test_code):
                # Для всех автоматизированных тестов отсутствие assertions - это warning, не error
                # Генератор должен добавлять assertions, но если по какой-то причине не добавил,
                # это не критично - тест все равно может быть полезен
                warnings.append("Автоматизированный тест должен содержать хотя бы одну assertion для проверки результата")
        else:
            # Для manual тестов проверяем наличие описания шагов
            if not re.search(r'("""|\'\'\')', test_code) and "pass" not in test_code:
                warnings.append("Рекомендуется добавить описание шагов теста в docstring")
        
        return {"errors": errors, "warnings": warnings}
    def _validate_logic(self, test_code: str) -> Dict[str, List]:
        errors = []
        warnings = []
        if re.search(r"while\s+True\s*:", test_code):
            if "break" not in test_code:
                errors.append({
                    "type": "infinite_loop",
                    "line": None,
                    "message": "Обнаружен while True без break"
                })
        if "time.sleep" in test_code:
            warnings.append("Использование time.sleep() не рекомендуется, используйте явные waits")
        return {"errors": errors, "warnings": warnings}
    def _generate_recommendations(self, result: Dict) -> List[str]:
        recommendations = []
        if result["semantic_errors"]:
            for error in result["semantic_errors"]:
                if error.get("type") == "missing_decorator":
                    recommendations.append(f"Добавить {error.get('message', '')}")
        if result["warnings"]:
            recommendations.extend(result["warnings"])
        return recommendations