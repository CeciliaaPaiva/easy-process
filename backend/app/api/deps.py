from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

# get_current_user e get_current_tenant serão implementados na Sprint 1 (S1-04)

__all__ = ["get_db"]


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session
