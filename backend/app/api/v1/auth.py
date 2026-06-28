import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


async def _unique_slug(db: AsyncSession, base: str) -> str:
    slug, counter = base, 1
    while True:
        exists = (
            await db.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if not exists:
            return slug
        slug = f"{base}-{counter}"
        counter += 1


def _build_token_response(user: User) -> TokenResponse:
    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse
)
async def register(
    data: RegisterRequest, db: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    slug = await _unique_slug(db, _slugify(data.company_name))

    tenant = Tenant(name=data.company_name, slug=slug)
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        role="admin",
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este e-mail já está cadastrado",
        ) from exc

    await db.refresh(user)
    return _build_token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest, db: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    # Mensagem genérica para não revelar se o e-mail existe
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Conta desativada",
        )

    return _build_token_response(user)


@router.post("/refresh")
async def refresh_token(data: RefreshRequest) -> dict[str, str]:
    try:
        payload = verify_token(data.refresh_token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado",
        ) from exc

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não é do tipo refresh",
        )

    token_data = {"sub": payload["sub"], "tenant_id": payload["tenant_id"]}
    return {"access_token": create_access_token(token_data), "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
