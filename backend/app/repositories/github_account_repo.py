from sqlalchemy.orm import Session

from app.models.github_account import GitHubAccount


class GitHubAccountRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: int):
        return (
            self.db.query(GitHubAccount)
            .filter(GitHubAccount.user_id == user_id)
            .first()
        )

    def get_by_github_user_id(self, github_user_id: int):
        return (
            self.db.query(GitHubAccount)
            .filter(
                GitHubAccount.github_user_id == github_user_id
            )
            .first()
        )

    def create(
        self,
        user_id: int,
        github_user_id: int,
        github_login: str,
        encrypted_token: str,
        scopes: str | None,
    ):
        account = GitHubAccount(
            user_id=user_id,
            github_user_id=github_user_id,
            github_login=github_login,
            access_token_encrypted=encrypted_token,
            scopes=scopes,
        )

        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update(
        self,
        account: GitHubAccount,
        github_login: str,
        encrypted_token: str,
        scopes: str | None,
    ):
        account.github_login = github_login
        account.access_token_encrypted = encrypted_token
        account.scopes = scopes

        self.db.commit()
        self.db.refresh(account)
        return account