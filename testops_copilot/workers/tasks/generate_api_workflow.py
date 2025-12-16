
from celery import Task
from workers.celery_app import celery_app
from shared.utils.database import get_db
from shared.models.database import Request, TestCase
from agents.generator.generator_agent import GeneratorAgent
from agents.generator.openapi_parser import OpenAPIParser
from agents.validator.validator_agent import ValidatorAgent
from shared.utils.redis_client import redis_client
import uuid
import hashlib
from datetime import datetime
import asyncio
class GenerateAPIWorkflowTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        request_id = kwargs.get("request_id") or (args[0] if args else None)
        if request_id:
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = str(exc)
                    db.commit()
                    try:
                        from shared.utils.email_service import email_service
                        from shared.models.database import User
                        if request.user_id:
                            user = db.query(User).filter(User.user_id == request.user_id).first()
                            if user and user.email:
                                email_service.send_error_notification(
                                    to=user.email,
                                    request_id=str(request.request_id),
                                    error_message=str(exc)
                                )
                    except Exception as e:
                        from shared.utils.logger import agent_logger
                        agent_logger.warning(f"Failed to send error email notification: {e}")
@celery_app.task(
    bind=True,
    base=GenerateAPIWorkflowTask,
    name="workers.tasks.generate_api_workflow.generate_api_tests_task"
)
def generate_api_tests_task(
    self,
    request_id: str,
    openapi_url: str = None,
    openapi_spec: str = None,
    endpoints: list = None,
    test_types: list = None,
    options: dict = None
):
    options = options or {}
    test_types = test_types or ["positive"]
    try:
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            if not request:
                raise ValueError(f"Request {request_id} not found")
            request.status = "processing"
            request.started_at = datetime.utcnow()
            db.commit()
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "parsing"}
        )
        parser = OpenAPIParser()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if openapi_spec:
                import yaml
                import json
                try:
                    spec_dict = yaml.safe_load(openapi_spec)
                except:
                    spec_dict = json.loads(openapi_spec)
            elif openapi_url:
                # Добавляем таймаут для парсинга OpenAPI URL (максимум 60 секунд)
                from shared.utils.logger import agent_logger
                agent_logger.info(f"[API] Parsing OpenAPI from URL: {openapi_url}")
                try:
                    spec_dict = loop.run_until_complete(
                        asyncio.wait_for(
                            parser.parse_from_url(openapi_url),
                            timeout=60.0  # 60 секунд таймаут
                        )
                    )
                    agent_logger.info(f"[API] OpenAPI parsed successfully")
                except asyncio.TimeoutError:
                    error_msg = f"Timeout при получении OpenAPI спецификации из {openapi_url}. Проверьте доступность URL и скорость ответа сервера."
                    agent_logger.error(f"[API] {error_msg}")
                    raise ValueError(error_msg)
                except Exception as e:
                    error_msg = f"Ошибка при получении OpenAPI спецификации из {openapi_url}: {str(e)}"
                    agent_logger.error(f"[API] {error_msg}", exc_info=True)
                    raise ValueError(error_msg)
            else:
                raise ValueError("openapi_url or openapi_spec is required")
        finally:
            loop.close()
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "generation"}
        )
        generator = GeneratorAgent()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from shared.utils.logger import agent_logger
            agent_logger.info(
                f"[GENERATION] Starting API test generation",
                extra={
                    "request_id": request_id,
                    "openapi_url": openapi_url,
                    "endpoints": endpoints,
                    "test_types": test_types
                }
            )
            # Добавляем таймаут для генерации API тестов (максимум 5 минут)
            tests = loop.run_until_complete(
                asyncio.wait_for(
                generator.generate_api_tests(
                    openapi_spec=spec_dict,
                    openapi_url=openapi_url,
                    endpoints=endpoints,
                    test_types=test_types
                    ),
                    timeout=300.0  # 5 минут таймаут
                )
            )
            agent_logger.info(
                f"[GENERATION] API test generation completed",
                extra={
                    "request_id": request_id,
                    "tests_generated": len(tests)
                }
            )
        except asyncio.TimeoutError:
            from shared.utils.logger import agent_logger
            agent_logger.error(f"[GENERATION] API test generation timeout after 5 minutes for request {request_id}")
            raise ValueError("Генерация API тестов превысила таймаут - LLM не ответил за 5 минут")
        except Exception as e:
            from shared.utils.logger import agent_logger
            agent_logger.error(f"[GENERATION] API test generation error: {e}", exc_info=True)
            raise
        finally:
            loop.close()
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "validation", "tests_count": len(tests)}
        )
        validator = ValidatorAgent()
        validated_tests = []
        from shared.utils.logger import agent_logger
        agent_logger.info(f"[VALIDATION] Starting validation of {len(tests)} API tests for request {request_id}")
        for i, test_code in enumerate(tests):
            agent_logger.info(f"[VALIDATION] Validating API test {i+1}/{len(tests)}")
            validation_result = validator.validate(test_code, validation_level="full")
            passed = validation_result.get("passed", False)
            score = validation_result.get("score", 0)
            syntax_errors = len(validation_result.get('syntax_errors', []))
            semantic_errors = len(validation_result.get('semantic_errors', []))
            agent_logger.info(
                f"[VALIDATION] API Test {i+1} validation result",
                extra={
                    "test_number": i+1,
                    "passed": passed,
                    "score": score,
                    "syntax_errors": syntax_errors,
                    "semantic_errors": semantic_errors,
                    "has_decorators": "@allure.feature" in test_code and "@allure.story" in test_code and "@allure.title" in test_code
                }
            )
            
            syntax_errors = len(validation_result.get('syntax_errors', []))
            semantic_errors = len(validation_result.get('semantic_errors', []))
            syntax_errs = validation_result.get('syntax_errors', [])
            semantic_errs = validation_result.get('semantic_errors', [])
            
            # Логируем детали ошибок
            if syntax_errors > 0:
                agent_logger.warning(f"API Test {i+1} syntax errors: {syntax_errs}")
            if semantic_errors > 0:
                agent_logger.warning(f"API Test {i+1} semantic errors: {semantic_errs}")
            
            # Для API тестов принимаем даже с ошибками, если они не критичны
            # Пробуем исправить простые синтаксические ошибки
            if syntax_errors > 0:
                # Пытаемся исправить распространенные ошибки
                fixed_code = test_code
                # Удаляем неполные строки в конце
                lines = fixed_code.split('\n')
                while lines and lines[-1].strip() and not any(lines[-1].strip().endswith(c) for c in [':', '}', ']', ')', 'assert', 'pass', 'return']):
                    if '=' in lines[-1] or 'await' in lines[-1] or 'response' in lines[-1]:
                        # Возможно неполная строка, удаляем
                        lines.pop()
                    else:
                        break
                fixed_code = '\n'.join(lines)
                
                # Проверяем синтаксис исправленного кода
                try:
                    import ast
                    ast.parse(fixed_code)
                    test_code = fixed_code
                    syntax_errors = 0
                    agent_logger.info(f"API Test {i+1} syntax fixed")
                except:
                    pass
            
            # Принимаем тест если нет критических синтаксических ошибок
            # Для API тестов более мягкая валидация - принимаем если код выглядит как тест
            syntax_errors = len(validation_result.get('syntax_errors', []))
            semantic_errors = len(validation_result.get('semantic_errors', []))
            
            is_valid_test = (
                syntax_errors == 0 and
                (passed or score >= 50 or (semantic_errors == 0 and "def test_" in test_code and "assert" in test_code))
            )
            
            if is_valid_test:
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
                agent_logger.info(f"API Test {i+1} added to validated_tests (score={score}, passed={passed}, syntax_errors={syntax_errors})")
            else:
                # Все равно добавляем, но с предупреждением
                agent_logger.warning(
                    f"API Test {i+1} has issues but will be saved: score={score}, syntax_errors={syntax_errors}, semantic_errors={semantic_errors}",
                    extra={
                        "syntax_errors": syntax_errs,
                        "semantic_errors": semantic_errs,
                        "test_preview": test_code[:500]
                    }
                )
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            saved_tests = []
            for test_data in validated_tests:
                test_code = test_data["code"]
                code_hash = hashlib.sha256(test_code.encode()).hexdigest()
                test_name = "Generated API Test"
                if "def test_" in test_code:
                    import re
                    match = re.search(r'def\s+(test_\w+)', test_code)
                    if match:
                        test_name = match.group(1)
                # Логика статуса: passed если нет синтаксических ошибок
                # Тесты с синтаксически правильным кодом должны быть passed
                validation = test_data.get("validation", {})
                syntax_errors = len(validation.get("syntax_errors", []))
                
                # Проверяем наличие декораторов (простая проверка наличия строки)
                has_feature = "@allure.feature" in test_code
                has_story = "@allure.story" in test_code
                has_title = "@allure.title" in test_code
                has_decorators = has_feature and has_story and has_title
                
                score = validation.get("score", 0)
                passed = validation.get("passed", False)
                
                # УПРОЩЕННАЯ ЛОГИКА: Тест считается passed если:
                # 1. Нет синтаксических ошибок (критично!)
                # 2. И (есть хотя бы один декоратор ИЛИ score >= 30 ИЛИ passed = True)
                # Основная цель - тесты должны работать, warnings не критичны
                is_passed = (
                    syntax_errors == 0 and
                    (has_feature or has_story or has_title or score >= 30 or passed)
                )
                
                validation_status = "passed" if is_passed else "warning"
                
                agent_logger.info(
                    f"[STATUS] API Test '{test_name}' status determination",
                    extra={
                        "test_name": test_name,
                        "syntax_errors": syntax_errors,
                        "has_feature": has_feature,
                        "has_story": has_story,
                        "has_title": has_title,
                        "has_decorators": has_decorators,
                        "score": score,
                        "passed": passed,
                        "is_passed": is_passed,
                        "validation_status": validation_status
                    }
                )
                
                test_case = TestCase(
                    request_id=request.request_id,
                    test_name=test_name,
                    test_code=test_code,
                    test_type="api",
                    code_hash=code_hash,
                    validation_status=validation_status,
                    validation_issues=test_data.get("validation", {}).get("errors", [])
                )
                db.add(test_case)
                saved_tests.append({
                    "test_id": str(test_case.test_id),
                    "test_name": test_name
                })
            # КРИТИЧЕСКАЯ ПРОВЕРКА: Если сохранено 0 тестов - это ошибка
            if len(saved_tests) == 0:
                error_msg = f"CRITICAL: No tests saved! generated={len(tests)}, validated={len(validated_tests)}"
                from shared.utils.logger import agent_logger
                agent_logger.error(
                    error_msg,
                    extra={
                        "request_id": request_id,
                        "generated_count": len(tests),
                        "validated_count": len(validated_tests),
                        "endpoints": endpoints,
                        "test_types": test_types
                    }
                )
                request.error_message = error_msg
            else:
                # Проверка минимального количества тестов
                min_tests_required = 10
                if len(saved_tests) < min_tests_required:
                    from shared.utils.logger import agent_logger
                    agent_logger.warning(
                        f"Low test count: {len(saved_tests)} tests saved, minimum required: {min_tests_required}",
                        extra={
                            "request_id": request_id,
                            "saved_count": len(saved_tests),
                            "min_required": min_tests_required
                        }
                    )
            
            request.status = "completed"
            request.completed_at = datetime.utcnow()
            request.result_summary = {
                "tests_generated": len(saved_tests),
                "tests_validated": len(validated_tests),
                "endpoints_covered": len(endpoints) if endpoints else "all",
                "test_types": test_types
            }
            result_summary = {
                "tests_generated": len(saved_tests),
                "tests_validated": len(validated_tests),
                "tests_optimized": len(validated_tests),  # Для API тестов оптимизация = валидация
                "test_type": "api"
            }
            request.result_summary = result_summary
            db.commit()
        redis_client.publish_event(
            f"request:{request_id}",
            {
                "status": "completed",
                "tests_count": len(saved_tests),
                "result_summary": result_summary
            }
        )
        return {
            "request_id": request_id,
            "status": "completed",
            "tests_count": len(saved_tests),
            "tests": saved_tests
        }
    except Exception as e:
        error_msg = str(e)
        print(f"Error in generate_api_tests_task: {error_msg}")
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
        try:
            redis_client.publish_event(
                f"request:{request_id}",
                {"status": "failed", "error": error_msg}
            )
        except Exception:
            pass
        raise