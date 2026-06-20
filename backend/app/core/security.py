from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import AppError

bearer_scheme = HTTPBearer(auto_error=False)


def require_admin_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> None:
    if settings.app_env == "development" and settings.admin_token == "change-me":
        return
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("UNAUTHORIZED", "缺少后台访问令牌", status_code=401)
    if credentials.credentials != settings.admin_token:
        raise AppError("FORBIDDEN", "后台访问令牌无效", status_code=403)
