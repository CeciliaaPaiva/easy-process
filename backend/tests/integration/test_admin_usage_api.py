import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.llm_usage_log import LlmUsageLog
from app.models.user import User
from tests.integration.conftest import register_user


async def _seed_usage(db_session, tenant_id: uuid.UUID, **overrides) -> LlmUsageLog:
    defaults = {
        "tenant_id": tenant_id,
        "process_id": None,
        "stage": "bpmn_generation",
        "model": "gemini-flash-lite-latest",
        "attempt": 1,
        "prompt_tokens": 1000,
        "output_tokens": 200,
        "cached_tokens": 0,
        "total_tokens": 1200,
        "estimated_cost_usd": 0.0001,
    }
    defaults.update(overrides)
    log = LlmUsageLog(**defaults)
    db_session.add(log)
    await db_session.commit()
    return log


class TestGetUsageSummary:
    async def test_requires_authentication(self, client):
        resp = await client.get("/api/v1/admin/usage")
        assert resp.status_code == 401

    async def test_non_admin_gets_403(self, client, db_session):
        auth = await register_user(client)
        user_id = uuid.UUID(auth["user"]["id"])

        # Rebaixa o usuário registrado (sempre criado como "admin") para
        # "viewer" direto no banco — não há endpoint para o próprio usuário
        # se rebaixar, e o invite não expõe a senha temporária para login.
        user = (
            await db_session.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        user.role = "viewer"
        db_session.add(user)
        await db_session.commit()

        resp = await client.get("/api/v1/admin/usage", headers=auth["headers"])
        assert resp.status_code == 403

    async def test_admin_sees_totals_and_breakdown(self, client, db_session):
        auth = await register_user(client)
        tenant_id = uuid.UUID(auth["user"]["tenant_id"])

        await _seed_usage(
            db_session,
            tenant_id,
            stage="transcription",
            prompt_tokens=500,
            output_tokens=50,
            total_tokens=550,
            estimated_cost_usd=0.00005,
        )
        await _seed_usage(
            db_session,
            tenant_id,
            stage="bpmn_generation",
            prompt_tokens=2000,
            output_tokens=800,
            cached_tokens=100,
            total_tokens=2800,
            estimated_cost_usd=0.0009,
        )

        resp = await client.get("/api/v1/admin/usage", headers=auth["headers"])
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_calls"] == 2
        assert data["total_prompt_tokens"] == 2500
        assert data["total_output_tokens"] == 850
        assert data["total_tokens"] == 3350
        assert data["total_estimated_cost_usd"] == pytest.approx(0.00095)

        stages = {row["stage"]: row for row in data["by_stage"]}
        assert stages["transcription"]["calls"] == 1
        assert stages["bpmn_generation"]["calls"] == 1
        assert stages["bpmn_generation"]["cached_tokens"] == 100

        assert len(data["recent_logs"]) == 2
        assert len(data["by_day"]) == 1  # ambos os seeds no mesmo dia (hoje)

    async def test_other_tenant_usage_not_visible(self, client, db_session):
        auth_a = await register_user(client)
        auth_b = await register_user(client)
        tenant_a = uuid.UUID(auth_a["user"]["tenant_id"])

        await _seed_usage(db_session, tenant_a)

        resp_b = await client.get("/api/v1/admin/usage", headers=auth_b["headers"])
        assert resp_b.status_code == 200
        assert resp_b.json()["total_calls"] == 0

    async def test_days_filter_excludes_older_logs(self, client, db_session):
        auth = await register_user(client)
        tenant_id = uuid.UUID(auth["user"]["tenant_id"])

        old_log = await _seed_usage(db_session, tenant_id)
        old_log.created_at = datetime.utcnow() - timedelta(days=60)
        db_session.add(old_log)
        await db_session.commit()

        resp = await client.get("/api/v1/admin/usage?days=30", headers=auth["headers"])
        assert resp.status_code == 200
        assert resp.json()["total_calls"] == 0

        resp_all = await client.get(
            "/api/v1/admin/usage?days=365", headers=auth["headers"]
        )
        assert resp_all.json()["total_calls"] == 1
