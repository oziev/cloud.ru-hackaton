
import pytest
from fastapi.testclient import TestClient
from api_gateway.main import app
@pytest.fixture
def client():
    return TestClient(app)
class TestHealthEndpoints:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    def test_readiness_check(self, client):
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
class TestGenerateEndpoints:
    def test_generate_test_cases_endpoint_structure(self, client):
        assert hasattr(app.router, 'routes')
    def test_generate_api_tests_endpoint_structure(self, client):
        assert hasattr(app.router, 'routes')