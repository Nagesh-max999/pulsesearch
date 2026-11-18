from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register(self, email: str, password: str, full_name: str | None) -> User:
        existing = await self.user_repo.get_by_email(email)
        if existing is not None:
            raise EmailAlreadyRegisteredError(email)
        return await self.user_repo.create(
            email=email, hashed_password=hash_password(password), full_name=full_name
        )

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()
        return user

    def issue_token(self, user: User) -> str:
        return create_access_token(subject=str(user.id))
