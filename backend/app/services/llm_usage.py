"""Instrumentação de custo/uso das chamadas ao Gemini.

Preço em USD por 1M tokens (input/output) para os modelos usados no pipeline.
Ajustar conforme a tabela oficial do Gemini API mudar.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

logger = logging.getLogger("llm_usage")

# USD por 1M tokens: (input, output). Cache hit é cobrado a uma fração do input.
# gemini-2.5-flash foi descontinuado para novas chaves (404 NOT_FOUND) — preço
# mantido na tabela só de referência histórica.
_PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "gemini-flash-lite-latest": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-flash-latest": (1.50, 9.00),
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


async def record_usage(
    stage: str,
    tenant_id: str | uuid.UUID | None,
    process_id: str | uuid.UUID | None,
    response: object,
    model_name: str,
    attempt: int = 1,
) -> LlmUsage:
    """Loga (via log_usage) e persiste o uso em app.models.LlmUsageLog para o
    painel administrativo. Abre sua própria sessão de banco — os serviços de
    IA são singletons sem sessão de requisição, então persistir aqui evita
    threadear uma AsyncSession por todos eles. Falha ao persistir nunca
    interrompe o pipeline: é instrumentação, não caminho crítico. Sem
    tenant_id (ex: chamadas diretas em testes) só loga, não persiste."""
    usage = log_usage(
        stage, str(process_id) if process_id else None, response, model_name, attempt
    )

    if tenant_id is None:
        return usage

    try:
        # Import tardio evita import circular (app.core.database -> ... -> llm_usage
        # não existe hoje, mas mantém este módulo importável sem app.models carregado).
        from app.core.database import AsyncSessionLocal
        from app.models.llm_usage_log import LlmUsageLog

        async with AsyncSessionLocal() as db:
            db.add(
                LlmUsageLog(
                    tenant_id=uuid.UUID(str(tenant_id)),
                    process_id=uuid.UUID(str(process_id)) if process_id else None,
                    stage=stage,
                    model=model_name,
                    attempt=attempt,
                    prompt_tokens=usage.prompt_tokens,
                    output_tokens=usage.output_tokens,
                    cached_tokens=usage.cached_tokens,
                    total_tokens=usage.total_tokens,
                    estimated_cost_usd=usage.estimated_cost_usd,
                )
            )
            await db.commit()
    except Exception:
        logger.exception("Falha ao persistir llm_usage_log (stage=%s)", stage)

    return usage
