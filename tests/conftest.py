import os
import sys
from collections.abc import Generator
from pathlib import Path

# Garante que o diretório backend esteja no sys.path mesmo ao rodar caminhos relativos
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configura banco em memória antes de qualquer importação de app/engine
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "testing"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def bind_test_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configura o engine e SessionLocal de teste de forma isolada via monkeypatch."""
    monkeypatch.setattr("app.db.session.engine", test_engine)
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.agents.resolver_graph.SessionLocal", TestingSessionLocal)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Pula testes com @pytest.mark.real_llm caso -m real_llm não seja passado."""
    markexpr = config.getoption("markexpr", default="")
    if "real_llm" not in markexpr:
        skip_real_llm = pytest.mark.skip(
            reason=(
                "Marcador 'real_llm' não especificado (-m real_llm). "
                "Chamadas pagas desativadas por padrão para proteger o orçamento de US$ 7,50."
            )
        )
        for item in items:
            if "real_llm" in item.keywords:
                item.add_marker(skip_real_llm)

