"""Instrumentação de custo/uso das chamadas ao Gemini.

Preço em USD por 1M tokens (input/output) para os modelos usados no pipeline.
Ajustar conforme a tabela oficial do Gemini API mudar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("llm_usage")

# USD por 1M tokens: (input, output). Cache hit é cobrado a uma fração do input.
_PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "gemini-flash-lite-latest": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}
_CACHE_HIT_DISCOUNT = 0.25  # tokens servidos do cache custam ~25% do preço de input


@dataclass
class LlmUsage:
    prompt_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int
    estimated_cost_usd: float


def extract_usage(response: object, model_name: str) -> LlmUsage:
    """Lê usage_metadata da resposta do Gemini e estima o custo em USD."""
    metadata = getattr(response, "usage_metadata", None)

    prompt_tokens = getattr(metadata, "prompt_token_count", None) or 0
    output_tokens = getattr(metadata, "candidates_token_count", None) or 0
    cached_tokens = getattr(metadata, "cached_content_token_count", None) or 0
    total_tokens = getattr(metadata, "total_token_count", None) or (
        prompt_tokens + output_tokens
    )

    input_price, output_price = _PRICING_PER_MILLION.get(model_name, (0.0, 0.0))
    uncached_prompt_tokens = max(prompt_tokens - cached_tokens, 0)
    cost = (
        uncached_prompt_tokens * input_price
        + cached_tokens * input_price * _CACHE_HIT_DISCOUNT
        + output_tokens * output_price
    ) / 1_000_000

    return LlmUsage(
        prompt_tokens=prompt_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
    )


def log_usage(
    stage: str,
    process_id: str | None,
    response: object,
    model_name: str,
    attempt: int = 1,
) -> LlmUsage:
    """Extrai e loga o uso de uma chamada ao Gemini. Deve ser chamado inclusive
    em tentativas que falharam na validação, para medir o custo real de retries."""
    usage = extract_usage(response, model_name)
    logger.info(
        "llm_usage stage=%s process_id=%s model=%s attempt=%d "
        "prompt_tokens=%d output_tokens=%d cached_tokens=%d "
        "total_tokens=%d estimated_cost_usd=%.6f",
        stage,
        process_id,
        model_name,
        attempt,
        usage.prompt_tokens,
        usage.output_tokens,
        usage.cached_tokens,
        usage.total_tokens,
        usage.estimated_cost_usd,
    )
    return usage
