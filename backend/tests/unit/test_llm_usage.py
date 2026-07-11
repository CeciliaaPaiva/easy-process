import uuid
from unittest.mock import MagicMock

import pytest

from app.services.llm_usage import extract_usage, log_usage, record_usage


def _make_response(
    prompt_tokens: int, output_tokens: int, cached_tokens: int = 0
) -> MagicMock:
    metadata = MagicMock()
    metadata.prompt_token_count = prompt_tokens
    metadata.candidates_token_count = output_tokens
    metadata.cached_content_token_count = cached_tokens
    metadata.total_token_count = prompt_tokens + output_tokens

    resp = MagicMock()
    resp.usage_metadata = metadata
    return resp


class TestExtractUsage:
    def test_extracts_token_counts(self):
        response = _make_response(prompt_tokens=1000, output_tokens=200)

        usage = extract_usage(response, "gemini-flash-lite-latest")

        assert usage.prompt_tokens == 1000
        assert usage.output_tokens == 200
        assert usage.total_tokens == 1200

    def test_estimates_positive_cost_for_known_model(self):
        response = _make_response(prompt_tokens=1000, output_tokens=200)

        usage = extract_usage(response, "gemini-flash-lite-latest")

        assert usage.estimated_cost_usd > 0

    def test_cached_tokens_reduce_cost_vs_uncached(self):
        uncached = extract_usage(
            _make_response(prompt_tokens=10_000, output_tokens=0),
            "gemini-flash-lite-latest",
        )
        cached = extract_usage(
            _make_response(prompt_tokens=10_000, output_tokens=0, cached_tokens=10_000),
            "gemini-flash-lite-latest",
        )

        assert cached.estimated_cost_usd < uncached.estimated_cost_usd

    def test_unknown_model_yields_zero_cost(self):
        response = _make_response(prompt_tokens=1000, output_tokens=200)

        usage = extract_usage(response, "modelo-desconhecido")

        assert usage.estimated_cost_usd == 0.0

    def test_missing_usage_metadata_defaults_to_zero(self):
        response = MagicMock()
        response.usage_metadata = None

        usage = extract_usage(response, "gemini-flash-lite-latest")

        assert usage.prompt_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.total_tokens == 0
        assert usage.estimated_cost_usd == 0.0


class TestLogUsage:
    def test_returns_extracted_usage(self):
        response = _make_response(prompt_tokens=500, output_tokens=100)

        usage = log_usage(
            "bpmn_generation", "proc-1", response, "gemini-flash-lite-latest"
        )

        assert usage.prompt_tokens == 500
        assert usage.output_tokens == 100

    def test_logs_with_correct_stage_and_attempt(self, caplog):
        import logging

        caplog.set_level(logging.INFO, logger="llm_usage")
        response = _make_response(prompt_tokens=500, output_tokens=100)

        log_usage(
            "bpmn_refinement", "proc-2", response, "gemini-flash-lite-latest", attempt=2
        )

        assert any(
            "bpmn_refinement" in r.getMessage() and "attempt=2" in r.getMessage()
            for r in caplog.records
        )


class _FakeSession:
    def __init__(self):
        self.added: list = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


class _FakeSessionLocal:
    def __init__(self):
        self.sessions: list[_FakeSession] = []

    def __call__(self):
        session = _FakeSession()
        self.sessions.append(session)
        return session


class TestRecordUsage:
    @pytest.mark.asyncio
    async def test_skips_persistence_without_tenant_id(self, mocker):
        fake_session_local = _FakeSessionLocal()
        mocker.patch("app.core.database.AsyncSessionLocal", fake_session_local)
        response = _make_response(prompt_tokens=100, output_tokens=50)

        usage = await record_usage(
            "transcription", None, "proc-1", response, "gemini-flash-lite-latest"
        )

        assert usage.prompt_tokens == 100
        assert fake_session_local.sessions == []

    @pytest.mark.asyncio
    async def test_persists_log_when_tenant_id_given(self, mocker):
        fake_session_local = _FakeSessionLocal()
        mocker.patch("app.core.database.AsyncSessionLocal", fake_session_local)
        tenant_id = uuid.uuid4()
        process_id = uuid.uuid4()
        response = _make_response(prompt_tokens=100, output_tokens=50, cached_tokens=10)

        usage = await record_usage(
            "bpmn_generation",
            tenant_id,
            process_id,
            response,
            "gemini-flash-lite-latest",
            attempt=2,
        )

        assert len(fake_session_local.sessions) == 1
        session = fake_session_local.sessions[0]
        assert session.committed is True
        assert len(session.added) == 1
        record = session.added[0]
        assert record.tenant_id == tenant_id
        assert record.process_id == process_id
        assert record.stage == "bpmn_generation"
        assert record.model == "gemini-flash-lite-latest"
        assert record.attempt == 2
        assert record.prompt_tokens == usage.prompt_tokens
        assert record.output_tokens == usage.output_tokens
        assert record.cached_tokens == usage.cached_tokens
        assert record.estimated_cost_usd == usage.estimated_cost_usd

    @pytest.mark.asyncio
    async def test_persists_with_string_ids(self, mocker):
        fake_session_local = _FakeSessionLocal()
        mocker.patch("app.core.database.AsyncSessionLocal", fake_session_local)
        tenant_id = uuid.uuid4()
        response = _make_response(prompt_tokens=10, output_tokens=5)

        await record_usage(
            "transcription",
            str(tenant_id),
            None,
            response,
            "gemini-flash-lite-latest",
        )

        record = fake_session_local.sessions[0].added[0]
        assert record.tenant_id == tenant_id
        assert record.process_id is None

    @pytest.mark.asyncio
    async def test_db_failure_does_not_raise(self, mocker):
        def _boom():
            raise RuntimeError("db down")

        mocker.patch("app.core.database.AsyncSessionLocal", _boom)
        response = _make_response(prompt_tokens=10, output_tokens=5)

        usage = await record_usage(
            "transcription",
            uuid.uuid4(),
            None,
            response,
            "gemini-flash-lite-latest",
        )

        assert usage.prompt_tokens == 10
