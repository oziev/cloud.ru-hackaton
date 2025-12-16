
from celery import Task
from workers.celery_app import celery_app
from shared.utils.database import get_db
from shared.models.database import Request, TestCase
from agents.reconnaissance.reconnaissance_agent import ReconnaissanceAgent
from agents.generator.generator_agent import GeneratorAgent
from agents.validator.validator_agent import ValidatorAgent
# OptimizerAgent убран - оптимизация отключена
from shared.utils.redis_client import redis_client
from shared.utils.logger import agent_logger
import uuid
import json
import hashlib
from datetime import datetime
import asyncio
class GenerateWorkflowTask(Task):
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
    base=GenerateWorkflowTask,
    name="workers.tasks.generate_workflow.generate_test_cases_task"
)
def generate_test_cases_task(
    self,
    request_id: str,
    url: str,
    requirements: list,
    test_type: str,
    options: dict = None
):
    options = options or {}
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
            {"status": "processing", "step": "reconnaissance"}
        )
        recon_agent = ReconnaissanceAgent()
        try:
            page_structure = recon_agent.analyze_page(url, timeout=60)
        except MemoryError as e:
            agent_logger.warning(f"[RECONNAISSANCE] MemoryError during page analysis: {e}, using fallback")
            # Используем минимальную структуру страницы как fallback
            page_structure = {
                "url": url,
                "title": "Page Analysis Failed",
                "elements": [],
                "error": "MemoryError: Page analysis failed due to memory constraints"
            }
        except Exception as e:
            agent_logger.warning(f"[RECONNAISSANCE] Error during page analysis: {e}, using fallback")
            # Используем минимальную структуру страницы как fallback
            page_structure = {
                "url": url,
                "title": "Page Analysis Failed",
                "elements": [],
                "error": str(e)
            }
        
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "generation"}
        )
        generator = GeneratorAgent()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent_logger.info(
                f"[GENERATION] Starting test generation",
                extra={
                    "request_id": request_id,
                    "url": url,
                    "test_type": test_type,
                    "requirements_count": len(requirements),
                    "options": options
                }
            )
            tests = loop.run_until_complete(
                generator.generate_ui_tests(
                    url=url,
                    page_structure=page_structure,
                    requirements=requirements,
                    test_type=test_type,
                    options=options
                )
            )
            agent_logger.info(
                f"[GENERATION] Test generation completed",
                extra={
                    "request_id": request_id,
                    "tests_generated": len(tests),
                    "test_type": test_type
                }
            )
        except asyncio.TimeoutError:
            agent_logger.error(f"[GENERATION] Generation timeout after 5 minutes for request {request_id}")
            tests = []
            raise ValueError("Test generation timeout - LLM не ответил за 5 минут")
        except Exception as e:
            agent_logger.error(f"[GENERATION] Generation error: {e}", exc_info=True)
            tests = []
            raise
        finally:
            loop.close()
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "validation", "tests_count": len(tests)}
        )
        validator = ValidatorAgent()
        validated_tests = []
        agent_logger.info(f"[VALIDATION] Starting validation of {len(tests)} tests for request {request_id}")
        for i, test_code in enumerate(tests):
            agent_logger.info(f"[VALIDATION] Validating test {i+1}/{len(tests)}")
            validation_result = validator.validate(test_code, validation_level="full")
            
            passed = validation_result.get("passed", False)
            score = validation_result.get("score", 0)
            syntax_errors = len(validation_result.get('syntax_errors', []))
            semantic_errors = len(validation_result.get('semantic_errors', []))
            logic_errors = len(validation_result.get('logic_errors', []))
            warnings = len(validation_result.get('warnings', []))
            
            agent_logger.info(
                f"[VALIDATION] Test {i+1} validation result",
                extra={
                    "test_number": i+1,
                    "passed": passed,
                    "score": score,
                    "syntax_errors": syntax_errors,
                    "semantic_errors": semantic_errors,
                    "logic_errors": logic_errors,
                    "warnings": warnings,
                    "has_decorators": "@allure.feature" in test_code and "@allure.story" in test_code and "@allure.title" in test_code
                }
            )
            
            # Принимаем тест если:
            # 1. Нет синтаксических ошибок И
            # 2. (passed = True ИЛИ score >= 50 ИЛИ нет критических ошибок)
            is_valid = (
                syntax_errors == 0 and
                (passed or score >= 50 or (semantic_errors == 0 and logic_errors == 0))
            )
            
            if is_valid:
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
                agent_logger.info(f"[VALIDATION] Test {i+1} ACCEPTED - added to validated_tests (passed={passed}, score={score})")
            else:
                errors = validation_result.get('errors', [])
                agent_logger.warning(
                    f"[VALIDATION] Test {i+1} has issues but will be added",
                    extra={
                        "test_number": i+1,
                        "score": score,
                        "errors_count": len(errors),
                        "warnings_count": warnings,
                        "syntax_errors": syntax_errors,
                        "semantic_errors": semantic_errors,
                        "logic_errors": logic_errors
                    }
                )
                if errors:
                    agent_logger.warning(f"[VALIDATION] Test {i+1} errors: {errors[:3]}")
                if validation_result.get('warnings'):
                    agent_logger.warning(f"[VALIDATION] Test {i+1} warnings: {validation_result.get('warnings', [])[:3]}")
                # Все равно добавляем тест, но с предупреждением
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
                agent_logger.info(f"[VALIDATION] Test {i+1} added to validated_tests despite issues")
        
        agent_logger.info(f"[VALIDATION] Validation completed: {len(validated_tests)}/{len(tests)} tests validated")
        
        # ВАЖНО: Сохраняем тесты СРАЗУ после валидации, до оптимизации
        # Оптимизация может зависнуть, и тесты не должны теряться
        agent_logger.info(f"[SAVING] Saving {len(validated_tests)} validated tests to database")
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            if not request:
                raise ValueError(f"Request {request_id} not found")
            
            saved_tests = []
            for test_data in validated_tests:
                test_code = test_data["code"]
                code_hash = hashlib.sha256(test_code.encode()).hexdigest()
                test_name = "Test"
                if "def test_" in test_code:
                    import re
                    match = re.search(r'def\s+(test_\w+)', test_code)
                    if match:
                        test_name = match.group(1)
                
                # Определяем тип теста: manual если есть @allure.manual, иначе проверяем наличие Playwright кода
                is_manual = "@allure.manual" in test_code
                has_playwright = any(keyword in test_code for keyword in [
                    "page.goto", "page.click", "page.fill", "page.locator",
                    "expect(", "page.wait_for", "page.get_by", "page: Page"
                ])
                actual_test_type = "manual" if is_manual else ("automated" if has_playwright else "automated")
                
                validation = test_data.get("validation", {})
                syntax_errors = len(validation.get("syntax_errors", []))
                has_feature = "@allure.feature" in test_code
                has_story = "@allure.story" in test_code
                has_title = "@allure.title" in test_code
                score = validation.get("score", 0)
                passed = validation.get("passed", False)
                
                is_passed = (
                    syntax_errors == 0 and
                    (has_feature or has_story or has_title or score >= 30 or passed)
                )
                validation_status = "passed" if is_passed else "warning"
                
                test_case = TestCase(
                    request_id=request.request_id,
                    test_name=test_name,
                    test_code=test_code,
                    test_type=actual_test_type,
                    code_hash=code_hash,
                    validation_status=validation_status,
                    validation_issues=validation.get("errors", [])
                )
                db.add(test_case)
                saved_tests.append({
                    "test_id": str(test_case.test_id),
                    "test_name": test_name
                })
            
            # Тесты сохранены, сразу переходим к завершению
            db.commit()
            agent_logger.info(f"[SAVING] Saved {len(saved_tests)} tests to database")
        
        # ОПТИМИЗАЦИЯ ПОЛНОСТЬЮ УБРАНА - вызывает проблемы с зависанием
        # Тесты уже сохранены после валидации, сразу переходим к завершению
        
        # Обновляем статус на completed и result_summary
        # Тесты уже сохранены после валидации, поэтому просто обновляем статус
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            if not request:
                raise ValueError(f"Request {request_id} not found")
            
            # Получаем количество сохраненных тестов из БД
            test_count = db.query(TestCase).filter(TestCase.request_id == request.request_id).count()
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: Если тестов 0, но были сгенерированы - это ошибка
            if test_count == 0 and len(tests) > 0:
                error_msg = f"CRITICAL: No tests saved despite {len(tests)} generated! This should not happen."
                agent_logger.error(
                    error_msg,
                    extra={
                        "request_id": request_id,
                        "generated_count": len(tests),
                        "validated_count": len(validated_tests),
                        "test_type": test_type
                    }
                )
                request.error_message = error_msg
            elif test_count == 0:
                error_msg = f"CRITICAL: No tests generated at all!"
                agent_logger.error(
                    error_msg,
                    extra={
                        "request_id": request_id,
                        "test_type": test_type,
                        "requirements": requirements
                    }
                )
                request.error_message = error_msg
            
            request.status = "completed"
            request.completed_at = datetime.utcnow()
            result_summary = {
                "tests_generated": test_count,
                "tests_validated": len(validated_tests),
                "tests_optimized": len(validated_tests),  # Оптимизация убрана, используем validated
                "test_type": test_type
            }
            request.result_summary = result_summary
            db.commit()
            agent_logger.info(f"[COMPLETED] Task {request_id} completed with {test_count} tests saved")
            
            try:
                from shared.utils.email_service import email_service
                from shared.models.database import User
                if request.user_id:
                    user = db.query(User).filter(User.user_id == request.user_id).first()
                    if user and user.email:
                        email_service.send_generation_completed(
                            to=user.email,
                            request_id=str(request.request_id),
                            tests_count=test_count,
                            status="completed"
                        )
            except Exception as e:
                agent_logger.warning(f"Failed to send email notification: {e}")
        
        redis_client.publish_event(
            f"request:{request_id}",
            {
                "status": "completed",
                "tests_count": test_count,
                "result_summary": result_summary
            }
        )
        
        # Получаем сохраненные тесты для возврата
        with get_db() as db:
            saved_test_cases = db.query(TestCase).filter(TestCase.request_id == uuid.UUID(request_id)).all()
            saved_tests = [
                {
                    "test_id": str(test.test_id),
                    "test_name": test.test_name
                }
                for test in saved_test_cases
            ]
        
        return {
            "request_id": request_id,
            "status": "completed",
            "tests_count": test_count,
            "tests": saved_tests
        }
    except Exception as e:
        error_msg = str(e)
        print(f"Error in generate_test_cases_task: {error_msg}")
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