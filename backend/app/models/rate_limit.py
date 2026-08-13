import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RateLimitBucket(Base):
    """Janela fixa de contagem para rate limiting (ver app/core/rate_limit.py).

    Uma linha por (key, window_start): `key` identifica o que está sendo
    limitado (ex: "upload:tenant:<uuid>", "login:ip:<ip>"), `window_start` é
    o início da janela de tempo à qual essa contagem pertence. Não há limpeza
    automática de linhas antigas — na escala atual (poucos usuários, poucos
    endpoints limitados) o crescimento da tabela é desprezível; revisar se
    isso mudar.
    """

    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint("key", "window_start", name="uq_rate_limit_bucket"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
