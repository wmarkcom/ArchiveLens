from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


class PlatformAuthenticationError(RuntimeError):
    """Raised when a platform rejects the configured login state."""


@dataclass(frozen=True)
class NormalizedPost:
    platform: str
    platform_post_id: str
    original_url: str
    published_at: datetime | None
    title: str | None = None
    full_text: str | None = None
    repost_text: str | None = None
    image_urls: list[str] = field(default_factory=list)
    video_cover_urls: list[str] = field(default_factory=list)
    source: str | None = None
    is_edited: bool = False
    raw_data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PageResult:
    items: list[NormalizedPost]
    next_cursor: str | None = None


class PlatformAdapter(ABC):
    platform: str

    @abstractmethod
    async def check_login(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def fetch_recent_posts(self, account_id: str, limit: int = 20) -> PageResult:
        raise NotImplementedError

    @abstractmethod
    async def fetch_history_page(
        self,
        account_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> PageResult:
        raise NotImplementedError

    def should_fetch_detail_for_monitor(self, post: NormalizedPost, *, is_new: bool) -> bool:
        return False

    async def enrich_posts_with_details(
        self,
        account_id: str,
        posts: list[NormalizedPost],
        *,
        max_count: int,
    ) -> list[NormalizedPost]:
        return posts
