from sqlalchemy import func, select

from ..models import User


class UserRepository:
    def __init__(self, db):
        self.db = db

    def create(self, username: str, email: str | None = None) -> User:
        user = User(username=username, email=email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_github_id(self, github_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.github_id == github_id))

    def create_github_user(self, username: str, github_id: int) -> User:
        user = User(username=username, github_id=github_id)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_refresh_jti(self, user: User, jti: str | None) -> None:
        """refresh_jti を更新する。None を渡すとトークンを失効させる。"""
        user.refresh_jti = jti
        self.db.commit()

    def count(self) -> int:
        return self.db.scalar(select(func.count()).select_from(User)) or 0
