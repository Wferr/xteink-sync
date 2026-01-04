from typing import Annotated, Optional

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from pydantic import BaseModel

from server.core import config
from server.core.data import load_tokens

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class User(BaseModel):
    id: str
    email: str
    nickname: str = "User"
    role: str = "user"
    is_active: bool = True


class LoginRequest(BaseModel):
    email: str
    password: str


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Security(security)] = None,
):
    if not config.SERVER_CONFIG["auth"]["enabled"]:
        # Return a dummy admin user if auth is disabled
        return User(id="admin", email="admin@example.com", nickname="Admin (Auth Disabled)")

    if not credentials:
        # Should be caught by Security(security) but just in case
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    token = credentials.credentials
    tokens = load_tokens()

    if token in tokens:
        user_data = tokens[token]
        uid = user_data.get("id", "unknown")

        return User(
            id=uid,
            email=user_data.get("email", ""),
            nickname=user_data.get("nickname", "User"),
        )

    raise HTTPException(
        status_code=401,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
