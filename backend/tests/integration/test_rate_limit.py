import asyncio
import types
import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.requests import Request

from app.core.database import get_db
from app.core.rate_limit import rate_limit_by_ip, rate_limit_by_tenant
from app.main import create_app


def _request(client_host: str) -> Request:
    return Request({"type": "http", "headers": [], "client": (client_host, 1)})


def _unique_prefix() -> str:
    # Cada teste usa um prefixo próprio pra não colidir com outros testes que
    # caiam na mesma janela de tempo.
    return f"test-{uuid.uuid4().hex[:8]}"


class TestRateLimitByIp:
    async def test_allows_up_to_the_limit(self, db_session):
        dep = rate_limit_by_ip(_unique_prefix(), limit=3, window_seconds=60)
        req = _request("10.0.0.1")
        for _ in range(3):
            await dep(request=req, db=db_session)  # não deve levantar

    async def test_blocks_after_limit(self, db_session):
        dep = rate_limit_by_ip(_unique_prefix(), limit=2, window_seconds=60)
        req = _request("10.0.0.2")
        await dep(request=req, db=db_session)
        await dep(request=req, db=db_session)

        with pytest.raises(HTTPException) as exc_info:
            await dep(request=req, db=db_session)
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    async def test_different_ips_have_independent_limits(self, db_session):
        dep = rate_limit_by_ip(_unique_prefix(), limit=1, window_seconds=60)
        await dep(request=_request("10.0.0.3"), db=db_session)
        await dep(request=_request("10.0.0.4"), db=db_session)  # chave diferente

    async def test_new_window_resets_the_count(self, db_session):
        dep = rate_limit_by_ip(_unique_prefix(), limit=1, window_seconds=1)
        req = _request("10.0.0.5")
        await dep(request=req, db=db_session)
        with pytest.raises(HTTPException):
            await dep(request=req, db=db_session)

        await asyncio.sleep(1.2)
        await dep(request=req, db=db_session)  # nova janela, não deve levantar


class TestRateLimitByTenant:
    async def test_blocks_after_limit(self, db_session):
        dep = rate_limit_by_tenant(_unique_prefix(), limit=2, window_seconds=60)
        user = types.SimpleNamespace(tenant_id=uuid.uuid4())
        await dep(current_user=user, db=db_session)
        await dep(current_user=user, db=db_session)

        with pytest.raises(HTTPException) as exc_info:
            await dep(current_user=user, db=db_session)
        assert exc_info.value.status_code == 429

    async def test_different_tenants_have_independent_limits(self, db_session):
        dep = rate_limit_by_tenant(_unique_prefix(), limit=1, window_seconds=60)
        user_a = types.SimpleNamespace(tenant_id=uuid.uuid4())
        user_b = types.SimpleNamespace(tenant_id=uuid.uuid4())
        await dep(current_user=user_a, db=db_session)
        await dep(current_user=user_b, db=db_session)  # chave diferente


class TestLoginEndpointEnforcesRateLimit:
    """Ao contrário da fixture `client` padrão (que desliga rate limiting
    pra não colidir entre testes — ver conftest.py), este app é montado sem
    esse override: exercita a dependency real presa no decorator da rota,
    com os limites de produção (settings.RATE_LIMIT_LOGIN_PER_15MIN)."""

    async def test_returns_429_after_configured_limit(self, engine):
        from app.core.config import settings

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        # IP fictício e único por execução: garante uma chave nova a cada
        # rodada do teste, sem esbarrar em janelas de execuções anteriores
        # (o prefixo "login" aqui é o mesmo do endpoint real de produção).
        fake_ip = f"203.0.113.{uuid.uuid4().int % 255}"
        headers = {"CF-Connecting-IP": fake_ip}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"email": "ninguem@teste.com", "password": "errada"}
            limit = settings.RATE_LIMIT_LOGIN_PER_15MIN
            for _ in range(limit):
                resp = await client.post(
                    "/api/v1/auth/login", json=payload, headers=headers
                )
                assert resp.status_code == 401  # credenciais inválidas, não 429 ainda

            resp = await client.post(
                "/api/v1/auth/login", json=payload, headers=headers
            )
            assert resp.status_code == 429
            assert "retry-after" in resp.headers
