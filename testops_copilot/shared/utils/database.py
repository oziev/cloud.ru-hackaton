
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Generator
from shared.config.settings import settings
from shared.models.database import Base
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def init_db():
    Base.metadata.create_all(bind=engine)
    from shared.models.database import User
    from uuid import UUID
    db = SessionLocal()
    try:
        default_users = db.query(User).filter(
            User.username.in_(["user1", "user2", "user3"])
        ).all()
        if len(default_users) < 3:
            default_users_data = [
                {
                    "user_id": UUID("00000000-0000-0000-0000-000000000001"),
                    "email": "user1@testops.local",
                    "username": "user1",
                    "full_name": "User 1",
                    "is_active": True,
                    "is_verified": True,
                    "api_key": "user1-api-key-2024",
                    "api_quota_daily": 1000
                },
                {
                    "user_id": UUID("00000000-0000-0000-0000-000000000002"),
                    "email": "user2@testops.local",
                    "username": "user2",
                    "full_name": "User 2",
                    "is_active": True,
                    "is_verified": True,
                    "api_key": "user2-api-key-2024",
                    "api_quota_daily": 1000
                },
                {
                    "user_id": UUID("00000000-0000-0000-0000-000000000003"),
                    "email": "user3@testops.local",
                    "username": "user3",
                    "full_name": "User 3",
                    "is_active": True,
                    "is_verified": True,
                    "api_key": "user3-api-key-2024",
                    "api_quota_daily": 1000
                }
            ]
            for user_data in default_users_data:
                existing = db.query(User).filter(User.user_id == user_data["user_id"]).first()
                if not existing:
                    user = User(**user_data)
                    db.add(user)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Ошибка при создании пользователей: {e}")
    finally:
        db.close()
@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Контекстный менеджер для работы с БД.
    Автоматически коммитит изменения при успехе или откатывает при ошибке.
    ВАЖНО: Не используйте объекты ORM после выхода из контекста!
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")
        raise
    finally:
        db.close()
def get_db_dependency():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def get_db_session() -> Session:
    db = SessionLocal()
    try:
        return db
    finally:
        pass