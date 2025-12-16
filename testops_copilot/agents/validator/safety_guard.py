
import ast
import re
import subprocess
import tempfile
import os
import resource
import sys
from typing import Dict, List, Any
from shared.utils.logger import agent_logger
from shared.config.settings import settings
class SafetyGuard:
    CRITICAL_BLACKLIST = [
        r'\beval\s\(',
        r'\bexec\s\(',
        r'\bcompile\s\(',
        r'\b__import__\s\(',
        r'\bos\.system\s\(',
        r'\bos\.popen\s\(',
        r'\bsubprocess\.',
        r'\bsocket\.',
        r'\bpickle\.loads?\s\(',
        r'\bsetattr\s\(',
        r'\bdelattr\s\(',
        r'\bglobals\s*\(',
        r'\blocals\s*\(',
    ]
    ALLOWED_IMPORTS = {
        'pytest', 'pytest_asyncio', 'allure', 'allure_commons', 'allure_pytest',
        'playwright', 'playwright.sync_api', 'playwright.async_api',
        'selenium', 'selenium.webdriver',
        'httpx', 'requests', 'aiohttp',
        'json', 're', 'datetime', 'time', 'uuid', 'math', 'random',
        'typing', 'typing_extensions', 'dataclasses', 'enum',
        'collections', 'functools', 'itertools',
        'asyncio', 'logging'
    }
    def validate(self, test_code: str) -> Dict[str, Any]:
        result = {
            "risk_level": "SAFE",
            "issues": [],
            "blocked_patterns": [],
            "action_taken": "allowed"
        }
        level1_result = self._static_analysis(test_code)
        if level1_result["blocked"]:
            result["risk_level"] = "CRITICAL"
            result["blocked_patterns"] = level1_result["blocked"]
            result["action_taken"] = "blocked"
            return result
        level2_result = self._ast_analysis(test_code)
        if level2_result["blocked"]:
            result["risk_level"] = "HIGH"
            result["blocked_patterns"] = level2_result["blocked"]
            result["action_taken"] = "blocked"
            return result
        if level2_result["warnings"]:
            result["risk_level"] = "MEDIUM"
            result["issues"] = level2_result["warnings"]
            result["action_taken"] = "warning"
        if settings.safety_guard_llm_analysis_enabled and result["risk_level"] in ["MEDIUM", "LOW"]:
            level3_result = self._llm_analysis(test_code)
            if level3_result.get("blocked"):
                result["risk_level"] = "HIGH"
                result["blocked_patterns"].extend(level3_result["blocked"])
                result["action_taken"] = "blocked"
                return result
            elif level3_result.get("warnings"):
                if result["risk_level"] == "SAFE":
                    result["risk_level"] = "LOW"
                result["issues"].extend(level3_result["warnings"])
        if settings.safety_guard_sandbox_enabled and result["risk_level"] in ["SAFE", "LOW", "MEDIUM"]:
            level4_result = self._sandbox_execution(test_code)
            if level4_result.get("blocked"):
                result["risk_level"] = "CRITICAL"
                result["action_taken"] = "blocked"
                result["blocked_patterns"].extend(level4_result["blocked"])
                return result
            elif level4_result.get("warnings"):
                if result["risk_level"] == "SAFE":
                    result["risk_level"] = "MEDIUM"
                result["issues"].extend(level4_result["warnings"])
        return result
    def _static_analysis(self, test_code: str) -> Dict[str, List]:
        blocked = []
        for pattern in self.CRITICAL_BLACKLIST:
            if re.search(pattern, test_code, re.IGNORECASE):
                blocked.append(pattern)
        return {"blocked": blocked}
    def _ast_analysis(self, test_code: str) -> Dict[str, List]:
        blocked = []
        warnings = []
        try:
            tree = ast.parse(test_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split('.')[0]
                        if module not in self.ALLOWED_IMPORTS:
                            blocked.append(f"Forbidden import: {module}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        if module not in self.ALLOWED_IMPORTS:
                            blocked.append(f"Forbidden import: {module}")
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                            blocked.append(f"Forbidden function call: {node.func.id}")
        except SyntaxError:
            pass
        return {"blocked": blocked, "warnings": warnings}
    def _behavioral_analysis(self, test_code: str) -> Dict[str, List]:
        warnings = []
        if re.search(r'open\s*\([^)]*["\']w["\']', test_code):
            warnings.append("File write operation detected")
        if re.search(r'(os\.remove|os\.unlink|shutil\.rmtree)', test_code):
            warnings.append("File deletion operation detected")
        return {"warnings": warnings}
    def _sandbox_execution(self, test_code: str) -> Dict[str, List]:
        blocked = []
        warnings = []
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                safe_code = self._wrap_in_sandbox(test_code)
                f.write(safe_code)
                temp_file = f.name
            try:
                max_memory = 100 * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env={**os.environ, 'PYTHONPATH': ''}
                )
                if result.returncode != 0:
                    if any(danger in result.stderr.lower() for danger in ['permission denied', 'access denied', 'forbidden']):
                        blocked.append("Sandbox execution detected restricted access attempt")
                        warnings.append(f"Execution error: {result.stderr[:200]}")
                else:
                    if result.stdout:
                        suspicious_patterns = [
                            'file://', 'http://', 'https://', 'ftp://',
                            '/etc/', '/var/', '/usr/', '/home/',
                            'socket', 'network', 'connection'
                        ]
                        for pattern in suspicious_patterns:
                            if pattern in result.stdout.lower():
                                warnings.append(f"Suspicious output detected: {pattern}")
            except subprocess.TimeoutExpired:
                blocked.append("Sandbox execution timeout - code took too long")
            except MemoryError:
                blocked.append("Sandbox execution memory limit exceeded")
            except Exception as e:
                agent_logger.warning(f"Sandbox execution error: {e}")
                warnings.append(f"Execution exception: {str(e)[:100]}")
            finally:
                try:
                    os.unlink(temp_file)
                except:
                    pass
        except Exception as e:
            agent_logger.error(f"Sandbox setup error: {e}", exc_info=True)
            warnings.append(f"Sandbox setup failed: {str(e)[:100]}")
        return {"blocked": blocked, "warnings": warnings}
    def _wrap_in_sandbox(self, test_code: str) -> str:
        wrapper = f"""import sys
import os
import resource

max_memory = 100 * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))

{self._indent_code(test_code)}
"""
        return wrapper
    def _indent_code(self, code: str, indent: int = 4) -> str:
        lines = code.split('\n')
        indented = [' ' * indent + line for line in lines]
        return '\n'.join(indented)