"""Rate limiting por janela fixa, com contagem atômica no Postgres.

Cada chamada limitada faz um UPSERT (`INSERT ... ON CONFLICT ... DO UPDATE`)
na tabela `rate_limit_buckets`, incrementando o contador da janela de tempo
atual para a chave em questão. É atômico mesmo com múltiplos workers do
gunicorn (o que uma trava em memória de processo não seria) e não exige
nenhuma infraestrutura nova além do Postgres que o app já usa.

Uso como dependency do FastAPI:
    @router.post(..., dependencies=[Depends(rate_limit_by_tenant("upload", ...))])
ou como parâmetro (quando outros dependencies do endpoint já resolvem
current_user/db, o FastAPI reaproveita o resultado — sem query duplicada):
    async def upload_audio(
        ...,
        current_user: User = Depends(get_current_user),
        _rl: None = Depends(rate_limit_by_tenant("upload", limit, window)),
    ): ...
"""

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.rate_limit import RateLimitBucket
from app.models.user import User


def client_ip(request: Request) -> str:
    """IP real do cliente por trás do Cloudflare Tunnel.

    O tráfego passa: navegador -> borda da Cloudflare -> Tunnel -> frontend
    (Next.js, que faz rewrite de /api/* pro backend) -> backend. A borda da
    Cloudflare injeta `CF-Connecting-IP`, que o Tunnel e o rewrite do Next
    preservam. Sem essa checagem, `request.client.host` seria sempre o IP
    interno do container do frontend — inutilizando o limite por IP (todo
    mundo cairia na mesma chave).
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _increment(
    db: AsyncSession, key: str, window_seconds: int
) -> tuple[int, int]:
    """Incrementa o contador da janela atual para `key`.

    Retorna (count, retry_after_seconds).
    """
    now = datetime.now(UTC)
    bucket_epoch = int(now.timestamp() // window_seconds) * window_seconds
    window_start = datetime.fromtimestamp(bucket_epoch, tz=UTC)
    retry_after = window_seconds - int(now.timestamp() - bucket_epoch)

    stmt = (
        insert(RateLimitBucket)
        .values(key=key, window_start=window_start, count=1)
        .on_conflict_do_update(
            constraint="uq_rate_limit_bucket",
            set_={"count": RateLimitBucket.count + 1},
        )
        .returning(RateLimitBucket.count)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one(), retry_after


def _too_many_requests(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Muitas requisições. Tente novamente em instantes.",
        headers={"Retry-After": str(retry_after)},
    )


def rate_limit_by_ip(
    prefix: str, limit: int, window_seconds: int
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Dependency: limita por IP do cliente. Para endpoints sem autenticação
    (registro, login), onde ainda não existe tenant pra usar como chave."""

    async def dependency(
        request: Request, db: AsyncSession = Depends(get_db_session)
    ) -> None:
        key = f"{prefix}:ip:{client_ip(request)}"
        count, retry_after = await _increment(db, key, window_seconds)
        if count > limit:
            raise _too_many_requests(retry_after)

    return dependency


def rate_limit_by_tenant(
    prefix: str, limit: int, window_seconds: int
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Dependency: limita por tenant autenticado. Para endpoints que geram
    custo de IA (upload de áudio, refinamento via chat)."""

    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> None:
        key = f"{prefix}:tenant:{current_user.tenant_id}"
        count, retry_after = await _increment(db, key, window_seconds)
        if count > limit:
            raise _too_many_requests(retry_after)

    return dependency
