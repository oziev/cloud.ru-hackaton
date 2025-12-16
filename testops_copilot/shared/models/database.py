
from sqlalchemy import (
    Column, String, Integer, Boolean, Text,
    DateTime, ForeignKey, DECIMAL, JSON, LargeBinary
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_AVAILABLE = True
except ImportError:
    VECTOR_AVAILABLE = False
    Vector = None
Base = declarative_base()
class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    api_key = Column(String(64), unique=True, nullable=True)
    api_quota_daily = Column(Integer, default=100)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    requests = relationship("Request", back_populates="user")
class Request(Base):
    __tablename__ = "requests"
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    url = Column(Text, nullable=False)
    requirements = Column(JSONB, nullable=False, default=[])
    test_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    result_summary = Column(JSONB, default={})
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String(255), nullable=True)
    langgraph_thread_id = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user = relationship("User", back_populates="requests")
    test_cases = relationship("TestCase", back_populates="request", cascade="all, delete-orphan")
    generation_metrics = relationship("GenerationMetric", back_populates="request", cascade="all, delete-orphan")
    coverage_analysis = relationship("CoverageAnalysis", back_populates="request", cascade="all, delete-orphan")
    security_audit_logs = relationship("SecurityAuditLog", back_populates="request", cascade="all, delete-orphan")
class TestCase(Base):
    __tablename__ = "test_cases"
    test_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False)
    test_name = Column(String(255), nullable=False)
    test_code = Column(Text, nullable=False)
    test_type = Column(String(20), nullable=False)
    allure_feature = Column(String(255), nullable=True)
    allure_story = Column(String(255), nullable=True)
    allure_title = Column(Text, nullable=True)
    allure_severity = Column(String(20), nullable=True)
    allure_tags = Column(JSONB, default=[])
    code_hash = Column(String(64), nullable=False)
    ast_hash = Column(String(64), nullable=True)
    if VECTOR_AVAILABLE:
        semantic_embedding = Column(Vector(768), nullable=True)
    else:
        semantic_embedding = Column(Text, nullable=True)
    covered_requirements = Column(JSONB, default=[])
    priority = Column(Integer, default=5)
    validation_status = Column(String(20), default="passed")
    validation_issues = Column(JSONB, default=[])
    safety_risk_level = Column(String(20), default="SAFE")
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(UUID(as_uuid=True), ForeignKey("test_cases.test_id", ondelete="SET NULL"), nullable=True)
    similarity_score = Column(DECIMAL(5, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    request = relationship("Request", back_populates="test_cases")
    security_audit_logs = relationship("SecurityAuditLog", back_populates="test_case", cascade="all, delete-orphan")
class GenerationMetric(Base):
    __tablename__ = "generation_metrics"
    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(50), nullable=False)
    step_number = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    llm_model = Column(String(100), nullable=True)
    llm_tokens_input = Column(Integer, nullable=True)
    llm_tokens_output = Column(Integer, nullable=True)
    llm_tokens_total = Column(Integer, nullable=True)
    llm_cost_usd = Column(DECIMAL(10, 6), nullable=True)
    status = Column(String(20), nullable=False)
    error_message = Column(Text, nullable=True)
    agent_metrics = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    request = relationship("Request", back_populates="generation_metrics")
class CoverageAnalysis(Base):
    __tablename__ = "coverage_analysis"
    coverage_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False)
    requirement_text = Column(Text, nullable=False)
    requirement_index = Column(Integer, nullable=False)
    is_covered = Column(Boolean, default=False)
    covering_tests = Column(JSONB, default=[])
    coverage_count = Column(Integer, default=0)
    coverage_score = Column(DECIMAL(5, 4), nullable=True)
    coverage_details = Column(JSONB, default={})
    has_gap = Column(Boolean, default=True)
    gap_description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    request = relationship("Request", back_populates="coverage_analysis")
class SecurityAuditLog(Base):
    __tablename__ = "security_audit_log"
    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False)
    test_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.test_id", ondelete="SET NULL"), nullable=True)
    security_layer = Column(String(20), nullable=False)
    risk_level = Column(String(20), nullable=False)
    issues = Column(JSONB, default=[])
    blocked_patterns = Column(JSONB, default=[])
    action_taken = Column(String(50), nullable=False)
    details = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    request = relationship("Request", back_populates="security_audit_logs")
    test_case = relationship("TestCase", back_populates="security_audit_logs")