
from typing import Dict, Any, List, Optional
import json
from shared.utils.llm_client import llm_client
from agents.test_plan.defect_analyzer import DefectAnalyzer
from shared.utils.logger import agent_logger
class TestPlanGeneratorAgent:
    SYSTEM_PROMPT = """Ты — senior QA engineer, специализирующийся на создании тест-планов.
Создавай структурированные тест-планы на основе требований и анализа дефектов.
Учитывай рискованные области и приоритизируй тесты на основе истории дефектов."""
    def __init__(self):
        self.defect_analyzer = DefectAnalyzer()
    async def generate_test_plan(
        self,
        requirements: List[str],
        project_key: str = None,
        components: List[str] = None,
        defect_analysis: Dict[str, Any] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        options = options or {}
        if defect_analysis is None and project_key:
            try:
                defect_analysis = await self.defect_analyzer.analyze_defect_history(
                    project_key=project_key,
                    days_back=options.get("days_back", 90),
                    components=components
                )
            except Exception as e:
                agent_logger.warning(f"Error analyzing defects: {e}")
                defect_analysis = None
        user_prompt = self._build_test_plan_prompt(
            requirements=requirements,
            defect_analysis=defect_analysis,
            components=components,
            options=options
        )
        try:
            response = await llm_client.generate(
                prompt=user_prompt,
                system_prompt=self.SYSTEM_PROMPT,
                model=None,
                temperature=0.3,
                max_tokens=4096
            )
            if not response or "choices" not in response or len(response["choices"]) == 0:
                agent_logger.error("Empty LLM response for test plan generation")
                return self._create_default_test_plan(requirements, defect_analysis)
            generated_content = response["choices"][0]["message"]["content"]
            test_plan = self._parse_test_plan(generated_content, requirements, defect_analysis)
            return test_plan
        except Exception as e:
            agent_logger.error(f"Error generating test plan: {e}", exc_info=True)
            return self._create_default_test_plan(requirements, defect_analysis)
    def prioritize_tests(
        self,
        tests: List[Dict[str, Any]],
        defect_analysis: Dict[str, Any] = None,
        risk_areas: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not tests:
            return []
        if risk_areas is None and defect_analysis:
            risk_areas = defect_analysis.get("risk_areas", [])
        prioritized_tests = []
        for test in tests:
            priority = self.defect_analyzer.calculate_priority(
                test_info=test,
                risk_areas=risk_areas,
                defect_history=defect_analysis.get("defects", []) if defect_analysis else None
            )
            test_copy = test.copy()
            test_copy["priority"] = priority
            test_copy["priority_source"] = "defect_analysis"
            prioritized_tests.append(test_copy)
        prioritized_tests.sort(key=lambda x: x.get("priority", 5), reverse=True)
        return prioritized_tests
    def _build_test_plan_prompt(
        self,
        requirements: List[str],
        defect_analysis: Dict[str, Any] = None,
        components: List[str] = None,
        options: Dict[str, Any] = None
    ) -> str:
        prompt_parts = [
            "Сгенерируй структурированный тест-план на основе следующих требований:",
            "",
            "ТРЕБОВАНИЯ:",
            *[f"{i+1}. {req}" for i, req in enumerate(requirements)],
            ""
        ]
        if components:
            prompt_parts.extend([
                "КОМПОНЕНТЫ ДЛЯ ТЕСТИРОВАНИЯ:",
                *[f"- {comp}" for comp in components],
                ""
            ])
        if defect_analysis:
            risk_areas = defect_analysis.get("risk_areas", [])
            patterns = defect_analysis.get("patterns", {})
            prompt_parts.extend([
                "АНАЛИЗ ДЕФЕКТОВ:",
                f"Всего дефектов: {patterns.get('total_defects', 0)}",
                ""
            ])
            if risk_areas:
                prompt_parts.append("РИСКОВАННЫЕ ОБЛАСТИ:")
                for area in risk_areas[:5]:
                    prompt_parts.append(
                        f"- {area['component']}: {area['defect_count']} дефектов, "
                        f"уровень риска {area['risk_level']}, приоритет {area.get('risk_score', 0)}"
                    )
                prompt_parts.append("")
            recommendations = defect_analysis.get("recommendations", [])
            if recommendations:
                prompt_parts.extend([
                    "РЕКОМЕНДАЦИИ НА ОСНОВЕ АНАЛИЗА:",
                    *[f"- {rec}" for rec in recommendations],
                    ""
                ])
        prompt_parts.extend([
            "Сгенерируй тест-план в следующем формате JSON:",
            "{",
            '  "title": "Название тест-плана",',
            '  "description": "Описание и цель",',
            '  "scope": ["Область 1", "Область 2"],',
            '  "test_cases": [',
            '    {',
            '      "id": "TC-001",',
            '      "name": "Название тест-кейса",',
            '      "description": "Описание",',
            '      "priority": 8,',
            '      "component": "Component Name",',
            '      "test_type": "functional",',
            '      "estimated_time": "30m",',
            '      "dependencies": []',
            '    }',
            '  ]',
            "}",
            "",
            "Приоритеты должны учитывать анализ дефектов и рискованные области."
        ])
        return "\n".join(prompt_parts)
    def _parse_test_plan(
        self,
        content: str,
        requirements: List[str],
        defect_analysis: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        try:
            json_match = None
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                if json_end > json_start:
                    json_match = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                if json_end > json_start:
                    json_match = content[json_start:json_end].strip()
            else:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_match = content[json_start:json_end]
            if json_match:
                test_plan = json.loads(json_match)
            else:
                test_plan = self._create_test_plan_from_text(content, requirements)
            if defect_analysis and "test_cases" in test_plan:
                test_plan["test_cases"] = self.prioritize_tests(
                    tests=test_plan["test_cases"],
                    defect_analysis=defect_analysis
                )
            test_plan["metadata"] = {
                "requirements_count": len(requirements),
                "defect_analysis_included": defect_analysis is not None,
                "generated_at": None
            }
            return test_plan
        except json.JSONDecodeError as e:
            agent_logger.warning(f"Error parsing test plan JSON: {e}")
            return self._create_default_test_plan(requirements, defect_analysis)
        except Exception as e:
            agent_logger.error(f"Error parsing test plan: {e}", exc_info=True)
            return self._create_default_test_plan(requirements, defect_analysis)
    def _create_test_plan_from_text(
        self,
        text: str,
        requirements: List[str]
    ) -> Dict[str, Any]:
        lines = text.split("\n")
        title = "Тест-план"
        description = ""
        test_cases = []
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "название" in line.lower() or "title" in line.lower():
                title = line.split(":")[-1].strip() if ":" in line else title
            elif "описание" in line.lower() or "description" in line.lower():
                description = line.split(":")[-1].strip() if ":" in line else description
            elif line.startswith("TC-") or line.startswith("test") or "тест" in line.lower():
                test_cases.append({
                    "id": f"TC-{len(test_cases)+1:03d}",
                    "name": line,
                    "description": "",
                    "priority": 5,
                    "component": "",
                    "test_type": "functional",
                    "estimated_time": "30m",
                    "dependencies": []
                })
        return {
            "title": title,
            "description": description or f"Тест-план для {len(requirements)} требований",
            "scope": requirements,
            "test_cases": test_cases
        }
    def _create_default_test_plan(
        self,
        requirements: List[str],
        defect_analysis: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        test_cases = []
        for i, req in enumerate(requirements):
            test_cases.append({
                "id": f"TC-{i+1:03d}",
                "name": f"Тест для требования: {req[:50]}",
                "description": req,
                "priority": 5,
                "component": "",
                "test_type": "functional",
                "estimated_time": "30m",
                "dependencies": []
            })
        if defect_analysis:
            test_cases = self.prioritize_tests(
                tests=test_cases,
                defect_analysis=defect_analysis
            )
        return {
            "title": "Тест-план",
            "description": f"Тест-план для {len(requirements)} требований",
            "scope": requirements,
            "test_cases": test_cases,
            "metadata": {
                "requirements_count": len(requirements),
                "defect_analysis_included": defect_analysis is not None,
                "generated_at": None
            }
        }