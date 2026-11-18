from arq import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_user, get_db
from app.core.config import get_settings
from app.core.rate_limit import rate_limit_by_ip
from app.models.user import User
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.repositories.password_reset_token_repo import PasswordResetTokenRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from app.services.email.factory import get_email_provider
from app.services.password_reset_service import InvalidResetTokenError, PasswordResetService
from app.services.seed_service import seed_demo_documents
from app.services.storage.factory import get_storage_provider

router = APIRouter(prefix="/api/auth", tags=["auth"])
_password_reset_rate_limit = rate_limit_by_ip(
    "password-reset", "rate_limit_password_reset_per_minute"
)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    service = AuthService(UserRepository(session))
    try:
        user = await service.register(payload.email, payload.password, payload.full_name)
        await session.commit()
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        ) from exc

    settings = get_settings()
    if settings.seed_demo_documents:
        # Real documents through the real pipeline (see seed_service.py) — not
        # fabricated search results — so a fresh account isn't an empty shell,
        # and the user sees the live processing pipeline in action immediately.
        await seed_demo_documents(
            user.id,
            DocumentRepository(session),
            JobRepository(session),
            get_storage_provider(),
            arq_pool,
            settings,
        )
        await session.commit()

    token = service.issue_token(user)
    return TokenResponse(access_token=token, expires_in_minutes=settings.jwt_expire_minutes)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    service = AuthService(UserRepository(session))
    try:
        user = await service.authenticate(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        ) from exc

    settings = get_settings()
    token = service.issue_token(user)
    return TokenResponse(access_token=token, expires_in_minutes=settings.jwt_expire_minutes)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_password_reset_rate_limit)],
)
async def forgot_password(
    payload: ForgotPasswordRequest, session: AsyncSession = Depends(get_db)
):
    service = PasswordResetService(
        UserRepository(session),
        PasswordResetTokenRepository(session),
        get_email_provider(),
        get_settings(),
    )
    await service.request_reset(payload.email)
    await session.commit()
    # Always the same response whether or not the email is registered — the
    # route must not let a caller distinguish "sent" from "no such account".
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", dependencies=[Depends(_password_reset_rate_limit)])
async def reset_password(payload: ResetPasswordRequest, session: AsyncSession = Depends(get_db)):
    service = PasswordResetService(
        UserRepository(session),
        PasswordResetTokenRepository(session),
        get_email_provider(),
        get_settings(),
    )
    try:
        await service.reset_password(payload.token, payload.new_password)
        await session.commit()
    except InvalidResetTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"message": "Password updated. You can now sign in with your new password."}
