"""
Concede/revoga acesso de administradora da plataforma (is_platform_admin).

Operação de banco, não uma feature de produto — não há toggle na UI de
propósito (ver docs/sprints/SPRINT-11-plano.md, S11-01).

Uso:
    docker compose exec backend python scripts/set_platform_admin.py <email> [--revoke]
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, "/app")

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


async def set_platform_admin(db: AsyncSession, email: str, *, grant: bool) -> None:
    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if not user:
        print(f"❌ Nenhum usuário encontrado com o e-mail '{email}'.")
        return

    user.is_platform_admin = grant
    await db.commit()
    action = "concedido a" if grant else "revogado de"
    print(f"✅ Acesso de administradora da plataforma {action} {email}.")


async def main() -> None:
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} <email> [--revoke]")
        sys.exit(1)

    email = sys.argv[1]
    grant = "--revoke" not in sys.argv[2:]

    async with AsyncSessionLocal() as db:
        await set_platform_admin(db, email, grant=grant)


if __name__ == "__main__":
    asyncio.run(main())
