from app.services.platform.base import PageResult, PlatformAdapter


class MockPlatformAdapter(PlatformAdapter):
    platform = "mock"

    async def check_login(self) -> bool:
        return True

    async def fetch_recent_posts(self, account_id: str, limit: int = 20) -> PageResult:
        return PageResult(items=[])

    async def fetch_history_page(
        self,
        account_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> PageResult:
        return PageResult(items=[], next_cursor=None)
