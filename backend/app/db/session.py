"""数据库引擎与会话（SQLAlchemy 2.0）。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def get_db():
    """FastAPI 依赖：提供数据库会话（Phase 2 路由通过 Depends(get_db) 使用）。"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
