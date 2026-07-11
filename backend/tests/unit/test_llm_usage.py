from unittest.mock import MagicMock

from app.services.llm_usage import extract_usage, log_usage


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
