
import pytest
from agents.optimizer.optimizer_agent import OptimizerAgent
class TestOptimizerAgent:
    @pytest.fixture
    def agent(self):
        return OptimizerAgent()
    def test_find_exact_duplicates(self, agent):
        tests = [
            {"test_id": "1", "test_code": "def test_a(): pass"},
            {"test_id": "2", "test_code": "def test_a(): pass"},
            {"test_id": "3", "test_code": "def test_b(): pass"}
        ]
        duplicates = agent._find_exact_duplicates(tests)
        assert len(duplicates) > 0
        assert any("1" in d["test_ids"] and "2" in d["test_ids"] for d in duplicates)
    def test_cosine_similarity(self, agent):
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = agent._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001
    def test_analyze_coverage(self, agent):
        tests = [
            {"test_id": "1", "test_code": "def test_req1(): pass"},
            {"test_id": "2", "test_code": "def test_req1(): pass"}
        ]
        requirements = ["req1", "req2"]
        coverage = agent._analyze_coverage(tests, requirements)
        assert "coverage_score" in coverage
        assert 0.0 <= coverage["coverage_score"] <= 1.0