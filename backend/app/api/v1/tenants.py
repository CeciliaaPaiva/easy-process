import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(tags=["tenants"])


class InviteRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=255)
    role: str = Field(default="analyst", pattern="^(admin|analyst|viewer)$")


class UpdateMemberRequest(BaseModel):
    role: str = Field(pattern="^(admin|analyst|viewer)$")


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem gerenciar membros",
        )


@router.get("/tenants/members", response_model=list[UserResponse])
async def list_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    rows = (
        (
            await db.execute(
                select(User)
                .where(
                    User.tenant_id == current_user.tenant_id,
                    User.is_active.is_(True),
                )
                .order_by(User.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [UserResponse.model_validate(u) for u in rows]


@router.post(
    "/tenants/invite",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    data: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    _require_admin(current_user)

    existing = (
        await db.execute(select(User).where(User.email == data.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já está em uso",
        )

    temp_password = uuid.uuid4().hex
    new_user = User(
        tenant_id=current_user.tenant_id,
        email=data.email,
        name=data.name,
        role=data.role,
        password_hash=hash_password(temp_password),
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse.model_validate(new_user)


@router.put("/tenants/members/{member_id}", response_model=UserResponse)
async def update_member(
    member_id: uuid.UUID,
    data: UpdateMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    _require_admin(current_user)

    member = (
        await db.execute(
            select(User).where(
                User.id == member_id,
                User.tenant_id == current_user.tenant_id,
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membro não encontrado")

    if member.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode alterar seu próprio papel",
        )

    member.role = data.role
    await db.commit()
    await db.refresh(member)
    return UserResponse.model_validate(member)


@router.delete("/tenants/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_admin(current_user)

    member = (
        await db.execute(
            select(User).where(
                User.id == member_id,
                User.tenant_id == current_user.tenant_id,
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membro não encontrado")

    if member.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode remover a si mesmo",
        )

    member.is_active = False
    await db.commit()
