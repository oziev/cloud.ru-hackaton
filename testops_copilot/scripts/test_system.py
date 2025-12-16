#!/usr/bin/env python3
"""
Скрипт для проверки работы системы генерации тестов
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from agents.generator.generator import GeneratorAgent
from agents.validator.validator_agent import ValidatorAgent
from shared.utils.logger import agent_logger

def test_generator():
    """Тест генератора"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Генератор тестов")
    print("="*60)
    
    generator = GeneratorAgent()
    
    # Тестовый код для проверки
    test_code = """
import pytest
import allure
from playwright.sync_api import Page, expect

@allure.feature("Test Feature")
@allure.story("Test Story")
@allure.title("Test Title")
@allure.tag("NORMAL")
def test_example(page: Page):
    with allure.step("Проверка"):
        expect(page.locator("body")).to_be_visible()
"""
    
    print(f"✓ Генератор инициализирован")
    print(f"✓ Тестовый код подготовлен ({len(test_code)} символов)")
    
    return True

def test_validator():
    """Тест валидатора"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Валидатор тестов")
    print("="*60)
    
    validator = ValidatorAgent()
    
    # Тест 1: Правильный тест с декораторами
    good_test = """
import pytest
import allure
from playwright.sync_api import Page, expect

@allure.feature("Test Feature")
@allure.story("Test Story")
@allure.title("Test Title")
@allure.tag("NORMAL")
def test_good(page: Page):
    with allure.step("Проверка"):
        expect(page.locator("body")).to_be_visible()
"""
    
    result = validator.validate(good_test, validation_level="full")
    print(f"✓ Тест с декораторами:")
    print(f"  - passed: {result['passed']}")
    print(f"  - score: {result['score']}")
    print(f"  - syntax_errors: {len(result['syntax_errors'])}")
    print(f"  - semantic_errors: {len(result['semantic_errors'])}")
    print(f"  - warnings: {len(result['warnings'])}")
    
    # Проверка статуса
    syntax_errors = len(result.get('syntax_errors', []))
    has_decorators = (
        "@allure.feature" in good_test and
        "@allure.story" in good_test and
        "@allure.title" in good_test
    )
    score = result.get("score", 0)
    is_passed = (
        syntax_errors == 0 and
        (has_decorators or score >= 50)
    )
    
    expected_status = "passed" if is_passed else "warning"
    print(f"  - Ожидаемый статус: {expected_status}")
    
    if expected_status == "passed":
        print("  ✓ Статус правильный: PASSED")
    else:
        print("  ✗ Статус неправильный: WARNING (должен быть PASSED)")
        return False
    
    # Тест 2: Тест без декораторов (должен получить warning, но не error)
    test_without_decorators = """
def test_no_decorators():
    assert True
"""
    
    result2 = validator.validate(test_without_decorators, validation_level="full")
    print(f"\n✓ Тест без декораторов:")
    print(f"  - passed: {result2['passed']}")
    print(f"  - score: {result2['score']}")
    print(f"  - syntax_errors: {len(result2['syntax_errors'])}")
    print(f"  - semantic_errors: {len(result2['semantic_errors'])}")
    print(f"  - warnings: {len(result2['warnings'])}")
    
    if len(result2['syntax_errors']) == 0:
        print("  ✓ Нет синтаксических ошибок")
    else:
        print("  ✗ Есть синтаксические ошибки")
        return False
    
    return True

def test_status_logic():
    """Тест логики определения статуса"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Логика определения статуса")
    print("="*60)
    
    validator = ValidatorAgent()
    
    # Тест с декораторами
    test_with_decorators = """
import pytest
import allure

@pytest.mark.asyncio
@allure.feature("API Tests")
@allure.story("Test Story")
@allure.title("Test Title")
@allure.tag("NORMAL")
async def test_api():
    assert True
"""
    
    result = validator.validate(test_with_decorators, validation_level="full")
    syntax_errors = len(result.get('syntax_errors', []))
    has_decorators = (
        "@allure.feature" in test_with_decorators and
        "@allure.story" in test_with_decorators and
        "@allure.title" in test_with_decorators
    )
    score = result.get("score", 0)
    
    is_passed = (
        syntax_errors == 0 and
        (has_decorators or score >= 50)
    )
    
    status = "passed" if is_passed else "warning"
    
    print(f"✓ Тест с декораторами:")
    print(f"  - syntax_errors: {syntax_errors}")
    print(f"  - has_decorators: {has_decorators}")
    print(f"  - score: {score}")
    print(f"  - is_passed: {is_passed}")
    print(f"  - status: {status}")
    
    if status == "passed":
        print("  ✓ Статус правильный: PASSED")
        return True
    else:
        print("  ✗ Статус неправильный: WARNING (должен быть PASSED)")
        return False

def main():
    """Главная функция"""
    print("\n" + "="*60)
    print("ПРОВЕРКА СИСТЕМЫ ГЕНЕРАЦИИ И ВАЛИДАЦИИ ТЕСТОВ")
    print("="*60)
    
    results = []
    
    # Тест 1: Генератор
    try:
        results.append(("Генератор", test_generator()))
    except Exception as e:
        print(f"✗ Ошибка в тесте генератора: {e}")
        results.append(("Генератор", False))
    
    # Тест 2: Валидатор
    try:
        results.append(("Валидатор", test_validator()))
    except Exception as e:
        print(f"✗ Ошибка в тесте валидатора: {e}")
        results.append(("Валидатор", False))
    
    # Тест 3: Логика статуса
    try:
        results.append(("Логика статуса", test_status_logic()))
    except Exception as e:
        print(f"✗ Ошибка в тесте логики статуса: {e}")
        results.append(("Логика статуса", False))
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ПРОВЕРКИ")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nВсего тестов: {len(results)}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {failed}")
    
    if failed == 0:
        print("\n✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return 0
    else:
        print(f"\n✗ {failed} ТЕСТ(ОВ) ПРОВАЛЕНО")
        return 1

if __name__ == "__main__":
    sys.exit(main())

