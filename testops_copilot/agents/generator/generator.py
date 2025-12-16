
from typing import Dict, Any, List
import re
from shared.utils.llm_client import llm_client
import asyncio
from .prompts import UI_SYSTEM_PROMPT, API_SYSTEM_PROMPT
class GeneratorAgent:
    def __init__(self):
        self.ui_system_prompt = UI_SYSTEM_PROMPT
        self.api_system_prompt = API_SYSTEM_PROMPT
    async def generate_ui_tests(
        self,
        url: str,
        page_structure: Dict[str, Any],
        requirements: List[str],
        test_type: str = "both",
        options: Dict[str, Any] = None
    ) -> List[str]:
        options = options or {}
        # Увеличиваем минимальное количество тестов - КРИТИЧЕСКИ ВАЖНО: минимум 10 тестов!
        manual_count = options.get("manual_count", 15)
        automated_count = options.get("automated_count", 20)  # Увеличено до 20 для гарантии минимум 10
        user_prompt = self._build_ui_prompt(url, page_structure, requirements, test_type, options)
        try:
            # Увеличиваем max_tokens для генерации большего количества тестов
            # Для 15+ тестов нужно больше токенов
            max_tokens = 12288 if test_type in ["manual", "both"] else 8192  # Увеличено для большего количества тестов
            response = await llm_client.generate(
                prompt=user_prompt,
                system_prompt=self.ui_system_prompt,
                model=None,
                temperature=0.3,
                max_tokens=max_tokens
            )
            if not response or "choices" not in response or len(response["choices"]) == 0:
                print("LLM response is empty or invalid")
                return []
            generated_code = response["choices"][0]["message"]["content"]
            from shared.utils.logger import agent_logger
            
            # Извлекаем код из markdown блоков если они есть
            if "```python" in generated_code:
                import re
                python_blocks = re.findall(r'```python\s*\n(.*?)```', generated_code, re.DOTALL)
                if python_blocks:
                    generated_code = '\n\n'.join(python_blocks)
                    agent_logger.info(f"[GENERATION] Extracted {len(python_blocks)} Python code blocks from markdown")
                else:
                    # Пробуем без "python" после ```
                    python_blocks = re.findall(r'```\s*\n(.*?)```', generated_code, re.DOTALL)
                    if python_blocks:
                        generated_code = '\n\n'.join(python_blocks)
                        agent_logger.info(f"[GENERATION] Extracted {len(python_blocks)} code blocks from markdown")
            
            agent_logger.info(
                f"[GENERATION] LLM generated code",
                extra={
                    "code_length": len(generated_code),
                    "test_type": test_type,
                    "url": url
                }
            )
            if len(generated_code) > 0:
                agent_logger.debug(f"[GENERATION] Generated code preview (first 500 chars): {generated_code[:500]}")
            tests = self._extract_tests_from_code(generated_code)
            expected_manual = options.get("manual_count", 15) if test_type in ["manual", "both"] else 0
            expected_automated = options.get("automated_count", 20) if test_type in ["automated", "both"] else 0  # Используем 20 из настроек выше
            expected_total = expected_manual + expected_automated if test_type == "both" else (expected_manual if test_type == "manual" else expected_automated)
            
            agent_logger.info(
                f"[GENERATION] Extracted {len(tests)} tests from generated code",
                extra={
                    "tests_count": len(tests),
                    "test_type": test_type,
                    "expected_manual": expected_manual,
                    "expected_automated": expected_automated,
                    "expected_total": expected_total,
                    "generated_code_length": len(generated_code),
                    "generated_code_preview": generated_code[:1000] if len(generated_code) > 0 else "EMPTY"
                }
            )
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: Если тесты не извлечены, но код был сгенерирован
            if len(tests) == 0 and len(generated_code) > 100:
                agent_logger.error(
                    f"[GENERATION] CRITICAL: No tests extracted but code was generated! Code preview: {generated_code[:2000]}",
                    extra={
                        "test_type": test_type,
                        "generated_code_length": len(generated_code),
                        "code_preview": generated_code[:2000]
                    }
                )
            
            # Проверка минимального количества тестов
            min_required = 10  # Абсолютный минимум
            if len(tests) < min_required:
                agent_logger.error(
                    f"[GENERATION] CRITICAL: Too few tests generated! Expected at least {min_required}, got {len(tests)}. Expected total was {expected_total}. Generated code preview: {generated_code[:3000]}",
                    extra={
                        "code_preview": generated_code[:3000],
                        "expected_total": expected_total,
                        "min_required": min_required,
                        "actual": len(tests),
                        "test_type": test_type
                    }
                )
            elif len(tests) < expected_total * 0.7:  # Допускаем 70% от ожидаемого
                agent_logger.warning(
                    f"[GENERATION] Low test count! Expected at least {expected_total}, got {len(tests)}. Generated code preview: {generated_code[:2000]}",
                    extra={
                        "code_preview": generated_code[:2000],
                        "expected": expected_total,
                        "actual": len(tests)
                    }
                )
            
            if len(tests) == 0:
                agent_logger.error(
                    f"[GENERATION] CRITICAL: No tests extracted! Generated code preview: {generated_code[:2000]}",
                    extra={"code_preview": generated_code[:2000], "full_code_length": len(generated_code)}
                )
            else:
                # Логируем информацию о каждом тесте
                for i, test in enumerate(tests):
                    has_decorators = "@allure.feature" in test and "@allure.story" in test and "@allure.title" in test
                    is_manual = "@allure.manual" in test
                    agent_logger.debug(
                        f"[GENERATION] Test {i+1} info",
                        extra={
                            "test_number": i+1,
                            "has_decorators": has_decorators,
                            "is_manual": is_manual,
                            "code_length": len(test)
                        }
                    )
            return tests
        except Exception as e:
            print(f"Error generating UI tests: {e}")
            import traceback
            traceback.print_exc()
            raise
    async def generate_api_tests(
        self,
        openapi_spec: Dict[str, Any] = None,
        openapi_url: str = None,
        endpoints: List[str] = None,
        test_types: List[str] = None
    ) -> List[str]:
        test_types = test_types or ["positive"]
        if openapi_url and not openapi_spec:
            from agents.generator.openapi_parser import OpenAPIParser
            parser = OpenAPIParser()
            openapi_spec = await parser.parse_from_url(openapi_url)
        if openapi_spec and self._is_cloud_ru_api(openapi_spec):
            from agents.generator.cloud_ru_api_generator import CloudRuAPIGenerator
            generator = CloudRuAPIGenerator()
            return await generator.generate_tests_for_endpoints(
                openapi_spec=openapi_spec,
                endpoints=endpoints,
                test_types=test_types
            )
        if not openapi_spec:
            raise ValueError("openapi_spec or openapi_url is required")
        user_prompt = self._build_api_prompt(openapi_spec, endpoints, test_types)
        try:
            # Увеличиваем max_tokens для генерации большего количества тестов
            max_tokens = 8192
            response = await llm_client.generate(
                prompt=user_prompt,
                system_prompt=self.api_system_prompt,
                model=None,
                temperature=0.3,
                max_tokens=max_tokens
            )
            if not response or "choices" not in response or len(response["choices"]) == 0:
                print("LLM response is empty or invalid")
                return []
            generated_code = response["choices"][0]["message"]["content"]
            tests = self._extract_tests_from_code(generated_code)
            from shared.utils.logger import agent_logger
            if len(tests) == 0:
                agent_logger.warning(f"No tests extracted from API generation. Code preview: {generated_code[:1000]}")
            else:
                # Постобработка API тестов
                processed_tests = []
                for i, test in enumerate(tests):
                    # Исправляем async функции
                    if "async with httpx.AsyncClient" in test and "async def" not in test:
                        test = test.replace("def test_", "async def test_")
                        # Добавляем @pytest.mark.asyncio если его нет
                        if "@pytest.mark.asyncio" not in test:
                            # Находим место после импортов, перед декораторами
                            lines = test.split('\n')
                            import_end = 0
                            for j, line in enumerate(lines):
                                if line.strip().startswith(('import ', 'from ')):
                                    import_end = j + 1
                                elif line.strip() and not line.strip().startswith('#'):
                                    break
                            lines.insert(import_end, "import pytest")
                            lines.insert(import_end + 1, "")
                            # Находим def и добавляем декоратор перед ним
                            for j in range(len(lines)):
                                if lines[j].strip().startswith('async def test_') or lines[j].strip().startswith('def test_'):
                                    if "@pytest.mark.asyncio" not in '\n'.join(lines[:j]):
                                        lines.insert(j, "@pytest.mark.asyncio")
                                    break
                            test = '\n'.join(lines)
                    
                    # Заменяем неопределенные переменные на конкретные значения
                    replacements = {
                        "VALID_PET": '{"id": 1, "name": "test-pet", "status": "available"}',
                        "INVALID_PET": '{"invalid": "data"}',
                        "IAM_TOKEN": '"test-token"',
                        "NOT_FOUND_PET_ID": "99999",
                        "get_token()": '"test-token"',
                        "token": '"test-token"',
                        "base_url": 'base_url="https://petstore.swagger.io/v2"'
                    }
                    for old, new in replacements.items():
                        test = test.replace(old, new)
                    
                    # Проверяем синтаксис
                    try:
                        import ast
                        ast.parse(test)
                        agent_logger.debug(f"API Test {i+1} syntax is valid after processing")
                        processed_tests.append(test)
                    except SyntaxError as e:
                        agent_logger.warning(f"API Test {i+1} has syntax error after processing: {e} at line {e.lineno}")
                        agent_logger.debug(f"Test {i+1} code (first 500 chars): {test[:500]}")
                        # Все равно добавляем, валидатор разберется
                        processed_tests.append(test)
                return processed_tests
            return tests
        except Exception as e:
            print(f"Error generating API tests: {e}")
            import traceback
            traceback.print_exc()
            raise
    def _is_cloud_ru_api(self, spec: Dict[str, Any]) -> bool:
        info = spec.get("info", {})
        title = info.get("title", "").lower()
        description = info.get("description", "").lower()
        return (
            "cloud.ru" in title or
            "cloud.ru" in description or
            "cloud.ru" in str(spec.get("servers", []))
        )
    def _build_ui_prompt(
        self,
        url: str,
        page_structure: Dict,
        requirements: List[str],
        test_type: str,
        options: Dict
    ) -> str:
        buttons = page_structure.get("buttons", [])[:10]
        inputs = page_structure.get("inputs", [])[:10]
        links = page_structure.get("links", [])[:10]
        automated_count = options.get("automated_count", 10)
        manual_count = options.get("manual_count", 15)
        
        test_type_instruction = ""
        if test_type == "both":
            test_type_instruction = f"""
КРИТИЧЕСКИ ВАЖНО: Сгенерируй ОБА типа тестов, КАЖДЫЙ ОТДЕЛЬНОЙ ФУНКЦИЕЙ:
1. Сначала ТОЧНО {manual_count} РУЧНЫХ тестов (каждый с @allure.manual декоратором, без Playwright кода, только описание шагов)
2. Затем ТОЧНО {automated_count} АВТОМАТИЗИРОВАННЫХ тестов (каждый с Playwright кодом)

ИТОГО ДОЛЖНО БЫТЬ {manual_count + automated_count} ОТДЕЛЬНЫХ ФУНКЦИЙ def test_...

Ручные тесты должны быть в формате (каждый отдельной функцией):
@allure.manual
@allure.feature("UI Tests")
@allure.story("Manual Test Cases")
@allure.title("Название теста")
@allure.tag("NORMAL")
def test_manual_1():
    \"\"\"Описание шагов теста\"\"\"
    pass

Автоматизированные тесты должны быть в формате (каждый отдельной функцией):
@allure.feature("UI Tests")
@allure.story("Automated Test Cases")
@allure.title("Название теста")
@allure.tag("NORMAL")
def test_automated_1(page: Page):
    with allure.step("Шаг 1"):
        page.goto("/")
    with allure.step("Проверка"):
        expect(page.locator("body")).to_be_visible()
"""
        elif test_type == "manual":
            test_type_instruction = f"""
КРИТИЧЕСКИ ВАЖНО: Сгенерируй ТОЧНО {manual_count} РУЧНЫХ тестов, КАЖДЫЙ ОТДЕЛЬНОЙ ФУНКЦИЕЙ def test_manual_...

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ ДЛЯ РУЧНЫХ ТЕСТОВ:
1. Каждый тест ДОЛЖЕН быть отдельной функцией def test_manual_...
2. Каждый тест ДОЛЖЕН иметь декоратор @allure.manual ПЕРЕД функцией
3. Каждый тест ДОЛЖЕН иметь полный набор декораторов ПЕРЕД функцией (@allure.feature, @allure.story, @allure.title, @allure.tag)
4. В функции должен быть docstring с описанием шагов теста
5. НЕ используй Playwright код в ручных тестах
6. МИНИМУМ {manual_count} ТЕСТОВ ОБЯЗАТЕЛЬНО!

Пример правильного ручного теста:
@allure.manual
@allure.feature("UI Tests")
@allure.story("Manual Test Cases")
@allure.title("Название теста")
@allure.tag("NORMAL")
@allure.severity(allure.severity_level.NORMAL)
def test_manual_1():
    \"\"\"
    Шаги теста:
    1. Открыть страницу
    2. Выполнить действие
    3. Проверить результат
    \"\"\"
    pass
"""
        elif test_type == "automated":
            test_type_instruction = f"""
🚫 КРИТИЧЕСКИ ВАЖНО: Сгенерируй ТОЧНО {automated_count} АВТОМАТИЗИРОВАННЫХ тестов, КАЖДЫЙ ОТДЕЛЬНОЙ ФУНКЦИЕЙ def test_automated_...

⚠️ МИНИМУМ {automated_count} ТЕСТОВ ОБЯЗАТЕЛЬНО! НЕ МЕНЬШЕ! ⚠️

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ ДЛЯ АВТОМАТИЗИРОВАННЫХ ТЕСТОВ:
1. Каждый тест ДОЛЖЕН иметь параметр page: Page: def test_xxx(page: Page):
2. Каждый тест ДОЛЖЕН содержать Playwright код (page.goto, page.click, expect, etc.)
3. НЕ используй pass или только комментарии!
4. НЕ используй docstring вместо кода!
5. Должен быть РАБОЧИЙ код, который можно запустить!

Пример ПРАВИЛЬНОГО автоматизированного теста:
@allure.feature("UI Tests")
@allure.story("Test Cases")
@allure.title("Название теста")
@allure.tag("NORMAL")
def test_automated_1(page: Page):
    with allure.step("Открытие страницы"):
        page.goto("/")
        expect(page.locator("body")).to_be_visible()
    with allure.step("Проверка элементов"):
        expect(page.locator('[data-testid="button"]')).to_be_visible()

Пример НЕПРАВИЛЬНОГО (это тест-план!):
def test_automated_1():
    \"\"\"Описание шагов\"\"\"
    # Шаг 1: Открыть страницу
    pass
❌ ЭТО ТЕСТ-ПЛАН! НЕ ГЕНЕРИРУЙ ТАК!

Каждый тест должен иметь полный набор декораторов ПЕРЕД функцией.
"""
        
        prompt = f"""🚫 ЗАПРЕЩЕНО ГЕНЕРИРОВАТЬ ТЕСТ-ПЛАНЫ! 🚫
Сгенерируй UI ТЕСТЫ (НЕ тест-планы!) для веб-страницы: {url}

🚫 КРИТИЧЕСКИ ВАЖНО: Генерируй ИМЕННО готовые тесты (функции def test_...), а НЕ тест-планы или описания!
🚫 НЕ генерируй списки тестов, описания, структуры - только РАБОЧИЙ Python КОД!
🚫 НЕ генерируй markdown, таблицы, списки - только функции def test_... с полным кодом!
✅ Генерируй ТОЛЬКО готовые Python функции с декораторами @allure.* и полным кодом!

Требования:
{chr(10).join(f"- {req}" for req in requirements)}

Тип тестов: {test_type}
{test_type_instruction}

КРИТИЧЕСКИ ВАЖНО: 
- Сгенерируй ТОЧНО указанное количество тестов ({manual_count} ручных и/или {automated_count} автоматизированных)
- МИНИМУМ {automated_count} автоматизированных тестов ОБЯЗАТЕЛЬНО! НЕ МЕНЬШЕ!
- Каждый тест должен быть отдельной функцией def test_...
- Не объединяй тесты в одну функцию
- Каждый тест должен иметь полный набор декораторов ПЕРЕД функцией
- Если сгенерируешь меньше {automated_count} тестов - это КРИТИЧЕСКАЯ ОШИБКА!

Структура страницы:
- Кнопки: {len(buttons)} найдено
- Поля ввода: {len(inputs)} найдено  
- Ссылки: {len(links)} найдено

Важно:
1. Все тесты должны использовать паттерн AAA (Arrange-Act-Assert)
2. Все тесты должны иметь полный набор Allure декораторов ПЕРЕД функцией:
   - @allure.feature("...")
   - @allure.story("...")
   - @allure.title("...")
   - @allure.tag("...")
3. Код должен быть валидным Python кодом без синтаксических ошибок
4. Автоматизированные тесты используют Playwright API и allure.step() для структурирования
5. Ручные тесты используют @allure.manual и описание шагов в docstring
6. КРИТИЧЕСКИ ВАЖНО: НЕ ПОВТОРЯЙ одинаковые действия много раз подряд
7. Если нужно выполнить несколько действий, используй циклы или переменные
8. Каждое действие должно быть осмысленным и проверять результат
9. Избегай множественных одинаковых кликов без проверки состояния
10. 🎯 КРИТИЧЕСКИ ВАЖНО: КАЖДЫЙ ТЕСТ ДОЛЖЕН БЫТЬ АБСОЛЮТНО УНИКАЛЬНЫМ!
    - НЕ генерируй тесты с одинаковой логикой или одинаковыми проверками
    - НЕ генерируй тесты, которые отличаются только названием функции
    - Каждый тест должен проверять РАЗНЫЕ аспекты функциональности
    - Используй РАЗНЫЕ селекторы, РАЗНЫЕ проверки, РАЗНЫЕ сценарии
    - Если генерируешь несколько тестов для одного элемента, каждый должен проверять РАЗНОЕ поведение
    - Каждый тест должен иметь УНИКАЛЬНУЮ логику, УНИКАЛЬНЫЕ проверки, УНИКАЛЬНЫЙ сценарий
    - Избегай шаблонности - каждый тест должен быть индивидуальным и проверять что-то свое

ЗАПРЕЩЕНО:
- Генерировать код с повторяющимися одинаковыми действиями без логики
- Множественные одинаковые клики подряд без проверки результата
- Пустые циклы или бессмысленные повторения
- Для ручных тестов использовать Playwright код
- Объединять несколько тестов в одну функцию
- Генерировать одинаковые тесты (с одинаковой логикой, селекторами, проверками)
- Дублировать тесты с незначительными изменениями (например, только меняя название)
- Генерировать тесты-шаблоны, которые отличаются только названием
- Копировать логику из одного теста в другой
"""
        return prompt
    def _build_api_prompt(
        self,
        openapi_spec: Dict[str, Any],
        endpoints: List[str] = None,
        test_types: List[str] = None
    ) -> str:
        test_types = test_types or ["positive"]
        info = openapi_spec.get("info", {})
        api_title = info.get("title", "API")
        api_version = info.get("version", "1.0.0")
        
        endpoint_info = []
        if endpoints:
            for path in endpoints:
                if path in openapi_spec.get("paths", {}):
                    endpoint_info.append(f"- {path}")
        else:
            paths = list(openapi_spec.get("paths", {}).keys())[:10]
            endpoint_info = [f"- {path}" for path in paths]
        
        prompt = f"""Сгенерируй API тесты для OpenAPI спецификации:

API: {api_title} v{api_version}

Endpoints для тестирования:
{chr(10).join(endpoint_info)}

Типы тестов: {', '.join(test_types)}

ВАЖНО: 
- Для каждого endpoint сгенерируй минимум 3-5 тестов разных типов
- Покрой все типы тестов: positive, negative (validation, auth, forbidden, not_found)
- Если endpoints не указаны, сгенерируй тесты для всех доступных endpoints (минимум 15 тестов)

Важно:
1. Все тесты должны использовать паттерн AAA (Arrange-Act-Assert)
2. Все тесты должны иметь полный набор Allure декораторов (@allure.feature, @allure.story, @allure.title, @allure.tag)
3. Использовать httpx.AsyncClient для асинхронных запросов
4. Код должен быть валидным Python кодом без синтаксических ошибок
5. Проверять статус коды и структуру ответов
6. Использовать @pytest.mark.asyncio для async функций
"""
        return prompt
    def _extract_tests_from_code(self, code: str) -> List[str]:
        """
        Извлекает тесты из сгенерированного кода и обеспечивает наличие обязательных элементов:
        - Allure декораторов
        - AAA паттерна
        - Валидного импорта
        - Дедупликация одинаковых тестов
        """
        tests = []
        test_pattern = r'def\s+(test_\w+)\s*\([^)]*\):'
        matches = list(re.finditer(test_pattern, code, re.MULTILINE))
        
        # Хеш-таблица для дедупликации тестов
        seen_tests = set()
        
        # Получаем импорты из начала кода
        import_lines = []
        for line in code.split('\n'):
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append(line)
            elif line.strip() and not line.strip().startswith('#') and not line.strip().startswith('"""'):
                break
        
        base_imports = '\n'.join(import_lines)
        
        # Определяем тип тестов по наличию ключевых слов
        is_api_test = "httpx" in code.lower() or "async" in code.lower() or "AsyncClient" in code
        is_ui_test = "playwright" in code.lower() or "Page" in code or "page.goto" in code
        
        # Обязательные импорты в зависимости от типа теста
        if is_api_test:
            required_imports = [
                "import pytest",
                "import allure",
                "import httpx",
                "import asyncio"
            ]
        else:
            required_imports = [
                "import pytest",
                "import allure",
                "from playwright.sync_api import Page, expect"
            ]
        
        if matches:
            for i, match in enumerate(matches):
                start = match.start()
                # Ищем конец функции более точно - ищем следующий def или конец файла
                if i + 1 < len(matches):
                    end = matches[i + 1].start()
                else:
                    end = len(code)
                
                # Извлекаем код функции, но проверяем что он полный
                test_code = code[start:end].strip()
                
                # Определяем тип теста СРАЗУ после извлечения кода
                is_manual = "@allure.manual" in test_code or "allure.manual" in test_code
                
                # Проверяем, что функция закрыта (есть хотя бы одна закрывающая скобка/двоеточие)
                # Если код обрезан, пытаемся найти конец функции по отступам
                lines = test_code.split('\n')
                if len(lines) > 0:
                    func_line = lines[0]
                    if 'def ' in func_line:
                        # Ищем конец функции по отступам
                        base_indent = len(func_line) - len(func_line.lstrip())
                        func_end = len(lines)
                        for j in range(1, len(lines)):
                            line = lines[j]
                            if line.strip() and not line.strip().startswith('#'):
                                line_indent = len(line) - len(line.lstrip())
                                # Если отступ меньше или равен базовому, это начало следующей функции/блока
                                if line_indent <= base_indent and (line.strip().startswith('def ') or line.strip().startswith('@')):
                                    func_end = j
                                    break
                        test_code = '\n'.join(lines[:func_end]).strip()
                        # Обновляем is_manual после изменения кода
                        is_manual = "@allure.manual" in test_code or "allure.manual" in test_code
                
                # Добавляем импорты если их нет
                if not base_imports or "import allure" not in base_imports:
                    imports = "\n".join(required_imports) + "\n\n"
                    test_code = imports + test_code
                elif base_imports:
                    # Проверяем наличие всех обязательных импортов
                    for imp in required_imports:
                        if imp not in base_imports:
                            base_imports += "\n" + imp
                    test_code = base_imports + "\n\n" + test_code
                
                # Проверяем наличие минимальных Allure декораторов
                function_match = re.search(r'def\s+(test_\w+)', test_code)
                if function_match:
                    func_name = function_match.group(1)
                    
                    # Проверяем наличие всех обязательных декораторов
                    has_feature = re.search(r'@allure\.feature\s*\(', test_code)
                    has_story = re.search(r'@allure\.story\s*\(', test_code)
                    has_title = re.search(r'@allure\.title\s*\(', test_code)
                    has_tag = re.search(r'@allure\.tag\s*\(', test_code)
                    
                    # Логируем если декораторы отсутствуют
                    if not (has_feature and has_story and has_title and has_tag):
                        from shared.utils.logger import agent_logger
                        missing = []
                        if not has_feature:
                            missing.append("feature")
                        if not has_story:
                            missing.append("story")
                        if not has_title:
                            missing.append("title")
                        if not has_tag:
                            missing.append("tag")
                        agent_logger.info(
                            f"[GENERATION] Adding missing decorators to test {i+1}",
                            extra={"missing_decorators": missing, "test_number": i+1}
                        )
                    
                    # Если хотя бы одного декоратора нет, добавляем все
                    if not (has_feature and has_story and has_title and has_tag):
                        test_title = func_name.replace('test_', '').replace('_', ' ').title()
                        # Определяем feature и story из названия теста
                        feature_name = "API Tests" if is_api_test else "UI Tests"
                        story_name = "Test Cases"
                        if "api" in func_name.lower() or "http" in func_name.lower():
                            feature_name = "API Tests"
                        elif "ui" in func_name.lower() or "page" in func_name.lower():
                            feature_name = "UI Tests"
                        
                        decorators = f'''@allure.feature("{feature_name}")
@allure.story("{story_name}")
@allure.title("{test_title}")
@allure.tag("NORMAL")
@allure.severity(allure.severity_level.NORMAL)
'''
                        # Для API тестов добавляем @pytest.mark.asyncio если нужно
                        if is_api_test and "@pytest.mark.asyncio" not in test_code and "async def" in test_code:
                            decorators = "@pytest.mark.asyncio\n" + decorators
                        
                        # Вставляем декораторы перед функцией
                        test_code = test_code.replace(function_match.group(0), decorators + function_match.group(0))
                
                # Для API тестов не добавляем allure.step с expect, так как это для UI
                # Проверяем наличие AAA структуры (хотя бы одну проверку)
                # is_manual уже определен выше (строка ~648)
                if not is_manual and "assert" not in test_code and "expect" not in test_code:
                    # Добавляем минимальную проверку если её нет
                    if "def test_" in test_code or "async def test_" in test_code:
                        lines = test_code.split('\n')
                        indent = "    "
                        inserted = False
                        for j, line in enumerate(lines):
                            if line.strip().startswith('def test_') or line.strip().startswith('async def test_'):
                                # Ищем тело функции (первая строка с отступом)
                                for k in range(j + 1, len(lines)):
                                    line_k = lines[k]
                                    if not line_k.strip() or line_k.strip().startswith('#'):
                                        continue
                                    # Если это строка с отступом (тело функции)
                                    if line_k.startswith(' ') or line_k.startswith('\t'):
                                        # Вставляем проверку в начало тела функции
                                        if is_api_test:
                                            # Для API тестов добавляем assert
                                            # Ищем место после response или в конце функции
                                            found_response = False
                                            for m in range(k, len(lines)):
                                                if "response" in lines[m].lower() and ("=" in lines[m] or "await" in lines[m]):
                                                    # Вставляем assert после response
                                                    response_indent = len(lines[m]) - len(lines[m].lstrip())
                                                    lines.insert(m + 1, ' ' * response_indent + 'assert response.status_code == 200  # TODO: Добавить проверку')
                                                    found_response = True
                                                    inserted = True
                                                    break
                                            if not found_response:
                                                # Вставляем в начало тела функции
                                                func_indent = len(line_k) - len(line_k.lstrip())
                                                lines.insert(k, ' ' * func_indent + 'assert True  # TODO: Добавить проверку')
                                                inserted = True
                                        else:
                                            # Для UI тестов добавляем expect
                                            func_indent = len(line_k) - len(line_k.lstrip())
                                            lines.insert(k, ' ' * func_indent + 'with allure.step("Проверка результата"):')
                                            lines.insert(k + 1, ' ' * (func_indent + 4) + 'expect(page.locator("body")).to_be_visible()  # TODO: Добавить проверку')
                                            inserted = True
                                        break
                                    # Если это начало следующей функции/блока без отступа
                                    elif not line_k.startswith(' ') and not line_k.startswith('\t'):
                                        # Вставляем проверку перед следующим блоком
                                        if is_api_test:
                                            prev_indent = len(lines[k-1]) - len(lines[k-1].lstrip()) if k > 0 else 4
                                            lines.insert(k, ' ' * prev_indent + 'assert True  # TODO: Добавить проверку')
                                        else:
                                            prev_indent = len(lines[k-1]) - len(lines[k-1].lstrip()) if k > 0 else 4
                                            lines.insert(k, ' ' * prev_indent + 'with allure.step("Проверка результата"):')
                                            lines.insert(k + 1, ' ' * (prev_indent + 4) + 'expect(page.locator("body")).to_be_visible()  # TODO: Добавить проверку')
                                        inserted = True
                                        break
                                if inserted:
                                    break
                        if inserted:
                            test_code = '\n'.join(lines)
                            # Обновляем is_manual после изменения кода
                            is_manual = "@allure.manual" in test_code or "allure.manual" in test_code
                
                # Проверка для автоматизированных тестов: должен быть Playwright код
                # НО: для manual тестов (@allure.manual) не требуем Playwright код
                # is_manual уже определен выше
                if not is_manual and not is_api_test:
                    # Для автоматизированных UI тестов проверяем наличие Playwright кода
                    has_page_param = "page: Page" in test_code or "(page:" in test_code
                    has_playwright_code = any(keyword in test_code for keyword in [
                        "page.goto", "page.click", "page.fill", "page.locator",
                        "expect(", "page.wait_for", "page.get_by"
                    ])
                    only_pass_or_comments = (
                        test_code.strip().endswith("pass") or
                        (test_code.count("def ") == 1 and 
                         test_code.count("page.") == 0 and 
                         test_code.count("expect") == 0 and
                         ("pass" in test_code or test_code.count("#") > 5))
                    )
                    
                    if not has_page_param or not has_playwright_code or only_pass_or_comments:
                        from shared.utils.logger import agent_logger
                        agent_logger.warning(
                            f"[GENERATION] Rejecting test without Playwright code (test plan detected): {func_name if 'func_name' in locals() else 'unknown'}",
                            extra={
                                "test_number": i+1,
                                "has_page_param": has_page_param,
                                "has_playwright_code": has_playwright_code,
                                "only_pass_or_comments": only_pass_or_comments
                            }
                        )
                        continue  # Пропускаем этот тест - это тест-план, а не тест
                # Для manual тестов (@allure.manual) принимаем даже если нет Playwright кода
                
                # Строгая дедупликация: проверяем, не является ли тест дубликатом
                # Создаем нормализованную версию кода для сравнения
                # Убираем пробелы, комментарии, декораторы, названия переменных, строки
                normalized_code = test_code
                
                # Убираем декораторы
                normalized_code = re.sub(r'@\w+\.\w+\([^)]*\)', '', normalized_code)
                normalized_code = re.sub(r'@\w+\s*', '', normalized_code)
                
                # Убираем комментарии
                normalized_code = re.sub(r'#.*', '', normalized_code)
                normalized_code = re.sub(r'""".*?"""', '', normalized_code, flags=re.DOTALL)
                normalized_code = re.sub(r"'''.*?'''", '', normalized_code, flags=re.DOTALL)
                
                # Убираем строки (заменяем на placeholder)
                normalized_code = re.sub(r'"[^"]*"', '"STRING"', normalized_code)
                normalized_code = re.sub(r"'[^']*'", "'STRING'", normalized_code)
                
                # Убираем названия функций и переменных (оставляем только структуру)
                normalized_code = re.sub(r'\bdef\s+\w+', 'def FUNC', normalized_code)
                normalized_code = re.sub(r'\btest_\w+', 'test_FUNC', normalized_code)
                
                # Убираем пробелы и приводим к нижнему регистру
                normalized_code = re.sub(r'\s+', ' ', normalized_code)
                normalized_code = normalized_code.strip().lower()
                
                # Извлекаем ключевые элементы для дополнительной проверки
                # (селекторы, методы, проверки)
                selectors = set(re.findall(r'locator\([^)]+\)', normalized_code))
                methods = set(re.findall(r'\.(goto|click|fill|expect|to_be_visible|to_have_text)', normalized_code))
                
                # Создаем составной ключ для более точного сравнения
                import hashlib
                structure_hash = hashlib.md5(normalized_code.encode()).hexdigest()
                selectors_hash = hashlib.md5(str(sorted(selectors)).encode()).hexdigest()
                methods_hash = hashlib.md5(str(sorted(methods)).encode()).hexdigest()
                composite_key = f"{structure_hash}_{selectors_hash}_{methods_hash}"
                
                # Проверяем, не видели ли мы уже этот тест
                if composite_key not in seen_tests:
                    seen_tests.add(composite_key)
                    tests.append(test_code)
                else:
                    from shared.utils.logger import agent_logger
                    agent_logger.warning(
                        f"[GENERATION] Skipping duplicate test: {func_name if 'func_name' in locals() else 'unknown'}",
                        extra={
                            "test_number": i+1,
                            "structure_hash": structure_hash[:8],
                            "selectors_count": len(selectors),
                            "methods_count": len(methods)
                        }
                    )
        else:
            # Если нет тестов, создаем один из всего кода
            if "import" not in code:
                code = "\n".join(required_imports) + "\n\n" + code
            tests.append(code)
        
        return tests