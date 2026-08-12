from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.async_api import APIRequestContext, async_playwright

from app.services.platform.base import NormalizedPost, PageResult, PlatformAdapter


XUEQIU_BASE_URL = "https://xueqiu.com"
XUEQIU_TIMELINE_ENDPOINT = f"{XUEQIU_BASE_URL}/statuses/user_timeline.json"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Apple Silicon Mac OS X 15_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class XueqiuCollectOptions:
    storage_state_path: Path
    uid: str
    page_no: int = 1
    limit: int = 20
    user_agent: str = DEFAULT_USER_AGENT


def extract_xueqiu_uid(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"\d+", value):
        return value

    parsed = urlparse(value if "://" in value else f"https://{value}")
    query = parse_qs(parsed.query)
    for key in ("uid", "user_id", "id"):
        candidate = query.get(key, [None])[0]
        if candidate and re.fullmatch(r"\d+", candidate):
            return candidate

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"u", "user"} and re.fullmatch(r"\d+", parts[1]):
        return parts[1]
    if parts and re.fullmatch(r"\d+", parts[0]):
        return parts[0]
    return None


def strip_xueqiu_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_xueqiu_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp, timezone.utc)


def has_xueqiu_auth_cookie(storage_state_path: str | Path) -> bool:
    path = Path(storage_state_path)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    cookies = state.get("cookies") or []
    return any(cookie.get("domain", "").endswith("xueqiu.com") for cookie in cookies)


def extract_status_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    statuses = payload.get("statuses") if isinstance(payload, dict) else None
    if isinstance(statuses, list):
        return [item for item in statuses if isinstance(item, dict)]
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        for key in ("statuses", "list", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def xueqiu_detail_url(item: dict[str, Any]) -> str:
    target = str(item.get("target") or "").strip()
    if target.startswith("http"):
        return target
    if target.startswith("/"):
        return f"{XUEQIU_BASE_URL}{target}"
    user_id = item.get("user_id") or item.get("uid")
    status_id = item.get("id") or item.get("status_id")
    if user_id and status_id:
        return f"{XUEQIU_BASE_URL}/{user_id}/{status_id}"
    return XUEQIU_BASE_URL


def image_urls_from_status(item: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    def add_url(value: Any) -> None:
        if isinstance(value, str) and value.startswith("http"):
            urls.append(value)

    add_url(item.get("pic"))
    for key in ("cover_pic", "image", "image_url"):
        add_url(item.get(key))

    for key in ("pics", "pic_urls", "images"):
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, str):
                    add_url(entry)
                elif isinstance(entry, dict):
                    for subkey in ("url", "src", "origin", "large"):
                        add_url(entry.get(subkey))

    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)
    return unique_urls


def normalize_xueqiu_status(item: dict[str, Any]) -> NormalizedPost:
    platform_post_id = str(item.get("id") or item.get("status_id"))
    title = strip_xueqiu_html(str(item.get("title") or "")) or None
    description = strip_xueqiu_html(str(item.get("description") or item.get("text") or ""))
    full_text = description
    if title and title not in full_text:
        full_text = f"{title}\n{full_text}".strip()

    retweeted = item.get("retweeted_status")
    repost_text = None
    if isinstance(retweeted, dict):
        repost_text = strip_xueqiu_html(
            str(retweeted.get("description") or retweeted.get("text") or retweeted.get("title") or "")
        ) or None

    return NormalizedPost(
        platform="xueqiu",
        platform_post_id=platform_post_id,
        original_url=xueqiu_detail_url(item),
        published_at=parse_xueqiu_datetime(item.get("created_at")),
        title=title,
        full_text=full_text,
        repost_text=repost_text,
        image_urls=image_urls_from_status(item),
        video_cover_urls=[],
        source=item.get("source"),
        is_edited=bool(item.get("edited_at")),
        raw_data=item,
    )


def next_page_from_payload(payload: dict[str, Any], current_page: int, item_count: int) -> str | None:
    max_page = payload.get("maxPage") or payload.get("max_page")
    try:
        if max_page is not None and current_page >= int(max_page):
            return None
    except (TypeError, ValueError):
        pass
    return str(current_page + 1) if item_count > 0 else None


async def parse_xueqiu_json_response(response: Any) -> dict[str, Any]:
    body = await response.body()
    content_type = response.headers.get("content-type", "")
    text = body.decode("utf-8", errors="replace")
    if text.lstrip().startswith("<"):
        raise RuntimeError("雪球接口返回 HTML，可能触发风控或登录态不可用，请刷新 xueqiu.json")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"雪球接口返回非 JSON：{exc.msg}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("雪球接口返回结构异常")
    if response.status >= 400:
        message = payload.get("message") or payload.get("error") or f"HTTP {response.status}"
        raise RuntimeError(f"雪球接口请求失败：{message}")
    if "json" not in content_type.lower() and not extract_status_items(payload):
        raise RuntimeError("雪球接口响应不是有效的时间线 JSON")
    return payload


async def fetch_timeline_payload(
    request: APIRequestContext,
    uid: str,
    page_no: int,
    limit: int,
) -> dict[str, Any]:
    response = await request.get(
        XUEQIU_TIMELINE_ENDPOINT,
        params={"user_id": uid, "page": str(page_no), "count": str(limit)},
        timeout=60000,
    )
    return await parse_xueqiu_json_response(response)


async def collect_xueqiu_posts(options: XueqiuCollectOptions) -> PageResult:
    async with async_playwright() as p:
        request = await p.request.new_context(
            storage_state=str(options.storage_state_path),
            user_agent=options.user_agent,
            extra_http_headers={
                "Referer": f"{XUEQIU_BASE_URL}/u/{options.uid}",
                "Accept": "application/json, text/plain, */*",
            },
        )
        try:
            payload = await fetch_timeline_payload(request, options.uid, options.page_no, options.limit)
            statuses = extract_status_items(payload)[: options.limit]
            return PageResult(
                items=[normalize_xueqiu_status(status) for status in statuses],
                next_cursor=next_page_from_payload(payload, options.page_no, len(statuses)),
            )
        finally:
            await request.dispose()


class XueqiuAdapter(PlatformAdapter):
    platform = "xueqiu"

    def __init__(self, storage_state_path: str | Path) -> None:
        self.storage_state_path = Path(storage_state_path)

    async def check_login(self, account_id: str | None = None) -> bool:
        if not self.storage_state_path.exists():
            return False
        if not has_xueqiu_auth_cookie(self.storage_state_path):
            return False
        if not account_id:
            return True
        try:
            await self.fetch_history_page(account_id, cursor="1", limit=1)
            return True
        except Exception:
            return False

    async def fetch_recent_posts(self, account_id: str, limit: int = 20) -> PageResult:
        return await self.fetch_history_page(account_id=account_id, cursor="1", limit=limit)

    async def fetch_history_page(
        self,
        account_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> PageResult:
        page_no = int(cursor or "1")
        return await collect_xueqiu_posts(
            XueqiuCollectOptions(
                storage_state_path=self.storage_state_path,
                uid=account_id,
                page_no=page_no,
                limit=limit,
            )
        )
