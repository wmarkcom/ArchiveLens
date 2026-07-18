import os
from functools import cached_property
from pathlib import Path

from dotenv import load_dotenv
from fastapi.responses import ORJSONResponse

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def default_auth_root(media_root: str) -> str:
    local_auth_root = PROJECT_ROOT / "auth"
    if local_auth_root.exists():
        return str(local_auth_root)
    if PROJECT_ROOT.exists():
        return str(local_auth_root)
    return str(Path(media_root).parent / "auth")


class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    admin_token: str = os.getenv("ADMIN_TOKEN", "change-me")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@postgres:5432/archivelens",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    media_root: str = os.getenv("MEDIA_ROOT", "/data/media")
    auth_root: str = os.getenv("AUTH_ROOT", default_auth_root(media_root))
    weibo_detail_fallback_limit: int = int(os.getenv("WEIBO_DETAIL_FALLBACK_LIMIT", "3"))
    weibo_detail_timeout_ms: int = int(os.getenv("WEIBO_DETAIL_TIMEOUT_MS", "10000"))
    weibo_list_timeout_ms: int = int(os.getenv("WEIBO_LIST_TIMEOUT_MS", "30000"))
    monitor_scan_interval: int = int(os.getenv("MONITOR_SCAN_INTERVAL", "30"))
    monitor_check_soft_time_limit: int = int(os.getenv("MONITOR_CHECK_SOFT_TIME_LIMIT", "180"))
    monitor_check_time_limit: int = int(os.getenv("MONITOR_CHECK_TIME_LIMIT", "240"))
    monitor_queue_warning_threshold: int = int(os.getenv("MONITOR_QUEUE_WARNING_THRESHOLD", "100"))
    monitor_queue_critical_threshold: int = int(os.getenv("MONITOR_QUEUE_CRITICAL_THRESHOLD", "500"))
    media_queue_warning_threshold: int = int(os.getenv("MEDIA_QUEUE_WARNING_THRESHOLD", "500"))
    media_queue_critical_threshold: int = int(os.getenv("MEDIA_QUEUE_CRITICAL_THRESHOLD", "2000"))
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "change-me")

    @cached_property
    def cors_origins(self) -> list[str]:
        raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def default_response_class(self) -> type[ORJSONResponse]:
        return ORJSONResponse

    def platform_auth_state_path(self, platform: str) -> Path:
        return Path(self.auth_root) / f"{platform}.json"


settings = Settings()
