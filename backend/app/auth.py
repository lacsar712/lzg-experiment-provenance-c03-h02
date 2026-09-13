from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# Pre-hashed for seed accounts (bcrypt of lab123456 / audit123456)
USERS = {
    "researcher": {
        "username": "researcher",
        "role": "researcher",
        "password_hash": pwd_context.hash("lab123456"),
    },
    "auditor": {
        "username": "auditor",
        "role": "auditor",
        "password_hash": pwd_context.hash("audit123456"),
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> dict | None:
    user = USERS.get(username)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return user


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        username = payload.get("sub")
        role = payload.get("role")
        if not username or username not in USERS:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌")
        return {"username": username, "role": role}
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌") from exc


def require_researcher(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "researcher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅研究员可执行命令")
    return user
