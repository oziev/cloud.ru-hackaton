
import pytest
from agents.validator.validator_agent import ValidatorAgent
class TestValidatorAgent:
    def test_init(self):
        agent = ValidatorAgent()
        assert agent is not None
    def test_validate_syntax_valid(self):
        agent = ValidatorAgent()
        valid_code = "def test_example(): assert True"
        result = agent._validate_syntax(valid_code)
        assert len(result["errors"]) == 0
    def test_validate_syntax_invalid(self):
        agent = ValidatorAgent()
        invalid_code = "def test_example( assert True"
        result = agent._validate_syntax(invalid_code)
        assert len(result["errors"]) > 0
    def test_validate_semantic_with_allure(self):
        agent = ValidatorAgent()
        code = "@allure.step\ndef test_example(): assert True"
        result = agent._validate_semantic(code)
        assert isinstance(result, dict)
    def test_validate_logic_valid(self):
        agent = ValidatorAgent()
        valid_code = "def test_example(): assert True"
        result = agent._validate_logic(valid_code)
        assert isinstance(result, dict)