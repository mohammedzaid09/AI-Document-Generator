import hmac

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.encryption import encrypt_github_token
from app.models.user import User
from app.repositories.github_account_repo import GitHubAccountRepository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService
from app.services.github_oauth_service import GitHubOAuthService


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    user = service.register_user(
        email=request.email,
        password=request.password,
    )

    return {
        "message": "User registered successfully",
        "user_id": user.id,
        "email": user.email,
    }


@router.post(
    "/login",
    response_model=AuthResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    access_token = service.login_user(
        email=request.email,
        password=request.password,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "created_at": current_user.created_at,
    }

@router.get("/github/login")
def github_login(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    try:
        service = GitHubOAuthService()
        authorization = service.create_authorization(
            current_user.id
        )

        response.set_cookie(
            key="github_oauth_state",
            value=authorization["state"],
            httponly=True,
            secure=False,  # Local HTTP development only
            samesite="lax",
            max_age=600,
            path="/api/auth/github",
        )

        return {
            "authorization_url": authorization[
                "authorization_url"
            ],
            "message": "Open the authorization URL to connect GitHub",
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.get("/github/callback")
def github_callback(
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    github_oauth_state: str | None = Cookie(
    default=None,
    alias="github_oauth_state"),
    db: Session = Depends(get_db),
):
    if error:
        raise HTTPException(
            status_code=400,
            detail="GitHub authorization was denied or cancelled",
        )

    if not code or not state or not github_oauth_state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth code or state",
        )

    if not hmac.compare_digest(state, github_oauth_state):
        raise HTTPException(
            status_code=400,
            detail="OAuth state validation failed",
        )

    service = GitHubOAuthService()
    user_id = service.get_user_id_from_state(state)

    if user_id is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state",
        )

    try:
        token_data = service.exchange_code(code)
        access_token = token_data["access_token"]
        github_user = service.get_user(access_token)

    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to complete GitHub authorization",
        ) from exc

    github_user_id = github_user.get("id")
    github_login = github_user.get("login")

    if not github_user_id or not github_login:
        raise HTTPException(
            status_code=502,
            detail="GitHub returned an incomplete user profile",
        )

    accounts = GitHubAccountRepository(db)

    linked_account = accounts.get_by_github_user_id(
        github_user_id
    )

    if linked_account and linked_account.user_id != user_id:
        raise HTTPException(
            status_code=409,
            detail="This GitHub account is linked to another user",
        )

    existing_account = accounts.get_by_user_id(user_id)

    encrypted_token = encrypt_github_token(access_token)
    scopes = token_data.get("scope", "")

    if existing_account:
        if existing_account.github_user_id != github_user_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Your application account is already linked "
                    "to a different GitHub account"
                ),
            )

        accounts.update(
            account=existing_account,
            github_login=github_login,
            encrypted_token=encrypted_token,
            scopes=scopes,
        )
    else:
        accounts.create(
            user_id=user_id,
            github_user_id=github_user_id,
            github_login=github_login,
            encrypted_token=encrypted_token,
            scopes=scopes,
        )

    if response is not None:
        response.delete_cookie(
            key="github_oauth_state",
            path="/api/auth/github",
        )

    return {
        "message": "GitHub account connected successfully",
        "github_login": github_login,
        "github_user_id": github_user_id,
        "scopes": scopes,
    }