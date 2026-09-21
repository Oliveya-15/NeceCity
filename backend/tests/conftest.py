"""
Pytest fixtures.

IMPORTANT: the DATABASE_URL override must happen before anything imports
`app.core.config` (which caches Settings via @lru_cache), so tests run
against `nececity_test`, never the development/demo database.
"""
import os

os.environ["DATABASE_URL"] = "postgresql+psycopg2://nececity:nececity@localhost:5432/nececity_test"
os.environ["ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.core.config import get_settings

get_settings.cache_clear()
settings = get_settings()

engine = create_engine(settings.sqlalchemy_database_uri, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    import app.models  # noqa: F401 register models
    Base.metadata.create_all(bind=engine)
    yield
    # Intentionally not dropping tables after the run so a developer can
    # inspect `nececity_test` after `pytest` if a test fails.


@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
