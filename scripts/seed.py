"""
Seed script de desenvolvimento — cria tenants e usuários iniciais.

Uso: make seed
     ou: docker compose exec backend python scripts/seed.py
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, "/app")

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402


async def create_tenant_user(
    db: AsyncSession,
    *,
    company: str,
    slug: str,
    email: str,
    password: str,
    name: str,
    role: str = "admin",
    is_platform_admin: bool = False,
) -> None:
    existing = (
        await db.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if existing:
        # Tenant já existe — ainda garante is_platform_admin no usuário do
        # seed (idempotente), pra rodar `make seed` de novo aplicar esse
        # ajuste em bancos de dev já populados antes dele existir.
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is not None and user.is_platform_admin != is_platform_admin:
            user.is_platform_admin = is_platform_admin
            print(f"  ✓ {company}: {email} — is_platform_admin={is_platform_admin} (atualizado)")
        else:
            print(f"  ⚠️  Tenant '{slug}' já existe — pulando.")
        return

    tenant = Tenant(name=company, slug=slug)
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password(password),
        name=name,
        role=role,
        is_platform_admin=is_platform_admin,
    )
    db.add(user)
    print(f"  ✓ {company}: {email} / {password} ({role}{', platform admin' if is_platform_admin else ''})")


async def seed() -> None:
    print("🌱 Iniciando seed de desenvolvimento...\n")
    async with AsyncSessionLocal() as db:
        await create_tenant_user(
            db,
            company="Demo Corp",
            slug="demo-corp",
            email="admin@demo.com",
            password="demo123",
            name="Admin Demo",
            role="admin",
            is_platform_admin=True,
        )
        await create_tenant_user(
            db,
            company="Acme Inc",
            slug="acme-inc",
            email="user@acme.com",
            password="acme123",
            name="Usuário Acme",
            role="analyst",
        )
        await db.commit()

    print("\n✅ Seed concluído!")


if __name__ == "__main__":
    asyncio.run(seed())
