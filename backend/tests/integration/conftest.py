import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.auth import login_rate_limit, register_rate_limit
from app.api.v1.processes import chat_rate_limit, upload_rate_limit
from app.core.database import Base, get_db
from app.main import create_app

TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or os.getenv(
    "DATABASE_URL", "sqlite+aiosqlite:///./test_integration.db"
)


@pytest.fixture(scope="session")
async def engine():
    _engine = create_async_engine(TEST_DB_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    # Nunca dropar tabelas aqui: quando TEST_DATABASE_URL não é definida, este
    # engine aponta para o mesmo banco de DATABASE_URL (necessário para que o
    # worker de background, que usa AsyncSessionLocal real, enxergue os dados
    # criados pelos testes). Um drop_all aqui já apagou o banco de dev antes.
    await _engine.dispose()


@pytest.fixture
async def db_session(engine):
    """Sessão de banco direta para testes que precisam seedar dados sem
    endpoint próprio (ex: LlmUsageLog, que só é escrito pelo pipeline de IA)."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    _app = create_app()
    _app.dependency_overrides[get_db] = override_get_db
    # Rate limiting é testado isoladamente em test_rate_limit.py (a fixture
    # `client` é reusada por toda a suíte via httpx.ASGITransport, que não
    # simula IPs distintos — sem esse override, todo mundo compartilharia a
    # mesma chave "ip:unknown" e testes não relacionados começariam a tomar
    # 429 dependendo da ordem/volume de execução).
    for dep in (
        register_rate_limit,
        login_rate_limit,
        upload_rate_limit,
        chat_rate_limit,
    ):
        _app.dependency_overrides[dep] = lambda: None

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    _app.dependency_overrides.clear()


async def register_user(client: AsyncClient) -> dict:
    uid = uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Test User {uid}",
            "email": f"user_{uid}@test.com",
            "password": "senha123",
            "company_name": f"Empresa {uid}",
        },
    )
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
        "email": f"user_{uid}@test.com",
        "password": "senha123",
    }
