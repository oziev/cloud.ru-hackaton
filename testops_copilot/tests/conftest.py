
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared.models.database import Base, Request, TestCase, User
@pytest.fixture
def mock_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
@pytest.fixture
def mock_redis():
    mock = MagicMock()
    mock.cache.get.return_value = None
    mock.cache.setex.return_value = True
    mock.pubsub.publish.return_value = True
    return mock
@pytest.fixture
def mock_llm_client():
    mock = MagicMock()
    mock.generate.return_value = "test code"
    mock.generate_embeddings.return_value = [0.1] * 768
    return mock
@pytest.fixture
def sample_request(mock_db):
    import uuid
    request = Request(
        request_id=uuid.uuid4(),
        url="https://example.com",
        requirements=["Test requirement"],
        test_type="automated",
        status="pending"
    )
    mock_db.add(request)
    mock_db.commit()
    return request
@pytest.fixture
def sample_test_case(mock_db, sample_request):
    import uuid
    test_case = TestCase(
        test_id=uuid.uuid4(),
        request_id=sample_request.request_id,
        test_name="test_sample",
        test_code="def test_sample(): pass",
        test_type="automated",
        code_hash="abc123"
    )
    mock_db.add(test_case)
    mock_db.commit()
    return test_case