
import secrets
from urllib.parse import urlencode

import httpx
from itsdangerous import URLSafeTimedSerializer, BadSignature

from app.core.config import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_REDIRECT_URI,
    JWT_SECRET_KEY,
)


class GitHubOAuthService:
    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_URL = "https://api.github.com/user"

    def __init__(self):
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            raise ValueError("GitHub OAuth credentials are not configured")

        self.state_serializer = URLSafeTimedSerializer(
            JWT_SECRET_KEY,
            salt="github-oauth-state",
        )

    def create_authorization(self, user_id: int):
        nonce = secrets.token_urlsafe(32)

        state = self.state_serializer.dumps({
            "nonce": nonce,
            "user_id": user_id,
        })

        params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "scope": "read:user user:email repo",
            "state": state,
        }

        return {
            "authorization_url": (
                f"{self.AUTHORIZE_URL}?{urlencode(params)}"
            ),
            "state": state,
        }


    def get_user_id_from_state(self, state: str) -> int | None:
        try:
            payload = self.state_serializer.loads(
                state,
                max_age=600,
            )

            user_id = payload.get("user_id")

            if isinstance(user_id, int) and user_id > 0:
                return user_id
            return None

        except (BadSignature, TypeError, AttributeError):
            return None

    def exchange_code(self, code: str) -> dict:
        response = httpx.post(
            self.TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
            timeout=20.0,
        )
        response.raise_for_status()

        data = response.json()

        if "error" in data or not data.get("access_token"):
            raise ValueError("GitHub token exchange failed")

        return data

    def get_user(self, access_token: str) -> dict:
        response = httpx.get(
            self.USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=20.0,
        )
        response.raise_for_status()
        return response.json()
