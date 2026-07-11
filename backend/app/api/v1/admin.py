from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.llm_usage_log import LlmUsageLog
from app.models.user import User
from app.schemas.admin import (
    UsageByDay,
    UsageByStage,
    UsageLogEntry,
    UsageSummaryResponse,
)

router = APIRouter(tags=["admin"])


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem acessar dados de uso da plataforma",
        )


@router.get("/admin/usage", response_model=UsageSummaryResponse)
async def get_usage_summary(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryResponse:
    """Resumo de custo/uso de tokens do Gemini, restrito a admins e sempre
    filtrado pelo tenant do usuário logado (isolamento multi-tenant)."""
    _require_admin(current_user)

    since = datetime.utcnow() - timedelta(days=days)
    tenant_filter = LlmUsageLog.tenant_id == current_user.tenant_id
    period_filter = LlmUsageLog.created_at >= since

    totals_row = (
        await db.execute(
            select(
                func.count(LlmUsageLog.id),
                func.coalesce(func.sum(LlmUsageLog.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.output_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.cached_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.total_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.estimated_cost_usd), 0.0),
            ).where(tenant_filter, period_filter)
        )
    ).one()

    by_stage_rows = (
        await db.execute(
            select(
                LlmUsageLog.stage,
                func.count(LlmUsageLog.id),
                func.coalesce(func.sum(LlmUsageLog.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.output_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.cached_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.total_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.estimated_cost_usd), 0.0),
            )
            .where(tenant_filter, period_filter)
            .group_by(LlmUsageLog.stage)
            .order_by(LlmUsageLog.stage)
        )
    ).all()

    day_expr = func.date(LlmUsageLog.created_at)
    by_day_rows = (
        await db.execute(
            select(
                day_expr,
                func.count(LlmUsageLog.id),
                func.coalesce(func.sum(LlmUsageLog.total_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.estimated_cost_usd), 0.0),
            )
            .where(tenant_filter, period_filter)
            .group_by(day_expr)
            .order_by(day_expr)
        )
    ).all()

    recent_rows = (
        (
            await db.execute(
                select(LlmUsageLog)
                .where(tenant_filter)
                .order_by(LlmUsageLog.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )

    return UsageSummaryResponse(
        total_calls=totals_row[0],
        total_prompt_tokens=totals_row[1],
        total_output_tokens=totals_row[2],
        total_cached_tokens=totals_row[3],
        total_tokens=totals_row[4],
        total_estimated_cost_usd=totals_row[5],
        by_stage=[
            UsageByStage(
                stage=row[0],
                calls=row[1],
                prompt_tokens=row[2],
                output_tokens=row[3],
                cached_tokens=row[4],
                total_tokens=row[5],
                estimated_cost_usd=row[6],
            )
            for row in by_stage_rows
        ],
        by_day=[
            UsageByDay(
                day=str(row[0]),
                calls=row[1],
                total_tokens=row[2],
                estimated_cost_usd=row[3],
            )
            for row in by_day_rows
        ],
        recent_logs=[UsageLogEntry.model_validate(r) for r in recent_rows],
    )
