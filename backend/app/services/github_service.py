import httpx
import base64
from sqlalchemy.orm import Session
from cryptography.fernet import InvalidToken

from urllib.parse import quote
from app.core.encryption import decrypt_github_token
from app.repositories.github_account_repo import (
    GitHubAccountRepository,
)


class GitHubService:
    BASE_URL = "https://api.github.com"

    def __init__(self, db: Session, user_id: int):
        account_repository = GitHubAccountRepository(db)

        account = account_repository.get_by_user_id(user_id)

        if not account:
            raise ValueError(
                "Connect your GitHub account before accessing repositories."
            )

        try:
            access_token = decrypt_github_token(
                account.access_token_encrypted
            )
        except (InvalidToken, ValueError):
            raise ValueError(
                "Unable to decrypt GitHub token. Check your encryption key."
            ) from None

        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    def get_repository(
        self,
        owner: str,
        repo: str,
    ) -> dict:

        url = f"{self.BASE_URL}/repos/{owner}/{repo}"

        response = httpx.get(
            url,
            headers=self.headers,
            timeout=10.0,
        )

        if response.status_code >= 400:
            raise ValueError(
                f"GitHub API error: {response.status_code} - {response.text}"
            )

        return response.json()

    def get_repository_tree(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
    ) -> dict:

        url = (
            f"{self.BASE_URL}/repos/"
            f"{owner}/{repo}/git/trees/{branch}"
        )

        response = httpx.get(
            url,
            headers=self.headers,
            params={"recursive": "true"},
            timeout=20.0,
        )

        if response.status_code >= 400:
            raise ValueError(
                f"GitHub API error: "
                f"{response.status_code} - {response.text}"
            )

        data = response.json()

        files = []
        directories = []

        for item in data.get("tree", []):

            if item["type"] == "blob":
                files.append({
                    "path": item["path"],
                    "sha": item["sha"],
                    "size": item.get("size"),
                })

            elif item["type"] == "tree":
                directories.append({
                    "path": item["path"],
                    "sha": item["sha"],
                })

        return {
            "files": files,
            "directories": directories,
            "truncated": data.get("truncated", False),
        }

    def get_commits(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        per_page: int = 30,
    ) -> list[dict]:

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits"

        response = httpx.get(
            url,
            headers=self.headers,
            params={
                "sha": branch,
                "per_page": per_page,
            },
            timeout=20.0,
        )

        if response.status_code >= 400:
            raise ValueError(
                f"GitHub API error: "
                f"{response.status_code} - {response.text}"
            )

        data = response.json()

        commits = []

        for commit in data:
            commits.append({
                "sha": commit["sha"],
                "message": commit["commit"]["message"],
                "author": (
                    commit["commit"]["author"]["name"]
                    if commit["commit"].get("author")
                    else None
                ),
                "author_email": (
                    commit["commit"]["author"]["email"]
                    if commit["commit"].get("author")
                    else None
                ),
                "date": (
                    commit["commit"]["author"]["date"]
                    if commit["commit"].get("author")
                    else None
                ),
                "url": commit["html_url"],
            })

        return commits

    def get_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 30,
    ) -> list[dict]:

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"

        response = httpx.get(
            url,
            headers=self.headers,
            params={
                "state": state,
                "per_page": per_page,
            },
            timeout=20.0,
        )

        if response.status_code >= 400:
            raise ValueError(
                f"GitHub API error: "
                f"{response.status_code} - {response.text}"
            )

        data = response.json()

        pull_requests = []

        for pull_request in data:
            pull_requests.append({
                "number": pull_request["number"],
                "title": pull_request["title"],
                "state": pull_request["state"],
                "author": (
                    pull_request["user"]["login"]
                    if pull_request.get("user")
                    else None
                ),
                "created_at": pull_request["created_at"],
                "updated_at": pull_request["updated_at"],
                "merged_at": pull_request["merged_at"],
                "url": pull_request["html_url"],
            })

        return pull_requests


    def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main",
        max_size: int = 500_000,
    ) -> dict:
        """Retrieve a text source file from a GitHub repository."""


        encoded_path = quote(path, safe="/")
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{encoded_path}"

        response = httpx.get(
            url,
            headers=self.headers,
            params={"ref": ref},
            timeout=30.0,
        )

        if response.status_code != 200:
            raise ValueError(
                f"GitHub API error retrieving {path}: "
                f"{response.status_code} - {response.text[:300]}"
            )

        result = response.json()

        if not isinstance(result, dict) or result.get("type") != "file":
            raise ValueError(f"{path} is not a regular file.")

        size = result.get("size", 0)

        if size > max_size:
            raise ValueError(
                f"File {path} is too large ({size} bytes). "
                f"Maximum allowed size is {max_size} bytes."
            )


        encoded_content = result.get("content", "")
        content = base64.b64decode(encoded_content).decode(
            "utf-8",
            errors="replace",
        )

        return {
            "path": path,
            "sha": result.get("sha"),
            "size": size,
            "content": content,
        }
