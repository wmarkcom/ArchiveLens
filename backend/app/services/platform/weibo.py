from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.async_api import BrowserContext, Page, async_playwright

from app.services.platform.base import NormalizedPost, PageResult, PlatformAdapter


WEIBO_BASE_URL = "https://weibo.com"
WEIBO_MBLOG_ENDPOINT = f"{WEIBO_BASE_URL}/ajax/statuses/mymblog"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Apple Silicon Mac OS X 15_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class WeiboCollectOptions:
    storage_state_path: Path
    uid: str
    page_no: int = 1
    limit: int = 20
    headless: bool = True
    detail_fallback_limit: int = 3
    detail_timeout_ms: int = 10000
    user_agent: str = DEFAULT_USER_AGENT


def parse_weibo_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def extract_weibo_uid(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"\d+", value):
        return value

    parsed = urlparse(value if "://" in value else f"https://{value}")
    query = parse_qs(parsed.query)
    for key in ("uid", "id"):
        candidate = query.get(key, [None])[0]
        if candidate and re.fullmatch(r"\d+", candidate):
            return candidate

    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None

    if parts[0] in {"u", "profile"} and len(parts) > 1 and re.fullmatch(r"\d+", parts[1]):
        return parts[1]
    if re.fullmatch(r"\d+", parts[0]):
        return parts[0]

    return None


def strip_weibo_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\u200b", "")
    text = text.replace("​​​", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*\.\.\.\s*展开$", "", text).strip()
    return text


def clean_weibo_detail_text(value: str | None) -> str:
    text = strip_weibo_html(value)
    if not text:
        return ""

    text = re.sub(r"\bTranslate content\b.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*喜欢我家.+?为TA助威.*$", "", text).strip()
    text = re.sub(r"\s*分享这条博文.*$", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_truncated_status(item: dict[str, Any]) -> bool:
    text = str(item.get("text") or "")
    text_raw = str(item.get("text_raw") or "")
    return "class=\"expand\"" in text or "...展开" in text or text_raw.endswith("​​​")


def weibo_detail_url(uid: str, item: dict[str, Any]) -> str:
    bid = item.get("mblogid") or item.get("bid") or item.get("mid") or item.get("id")
    return f"{WEIBO_BASE_URL}/{uid}/{bid}"


def normalize_weibo_image_url(url: str) -> str:
    if not url:
        return url
    return re.sub(r"/orj\d+/", "/mw2000/", url)


def is_content_image_url(url: str) -> bool:
    if not url.startswith("http"):
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "sinaimg.cn" not in host:
        return False
    if host.startswith("tva") or host.startswith("tvax"):
        return False
    lowered = url.lower()
    return "/upload/" not in lowered and "vvip" not in lowered


def image_urls_from_status(item: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    for pic in item.get("pics") or []:
        candidates = [
            pic.get("large", {}).get("url") if isinstance(pic.get("large"), dict) else None,
            pic.get("url"),
            pic.get("thumbnail", {}).get("url") if isinstance(pic.get("thumbnail"), dict) else None,
        ]
        for candidate in candidates:
            if candidate and is_content_image_url(candidate):
                urls.append(normalize_weibo_image_url(candidate))
                break

    for pic_id in item.get("pic_ids") or []:
        if not pic_id:
            continue
        urls.append(f"https://wx1.sinaimg.cn/mw2000/{pic_id}.jpg")

    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)
    return unique_urls


def video_cover_urls_from_status(item: dict[str, Any]) -> list[str]:
    page_info = item.get("page_info") or {}
    media_info = page_info.get("media_info") or {}
    candidates = [
        page_info.get("page_pic", {}).get("url") if isinstance(page_info.get("page_pic"), dict) else None,
        media_info.get("cover_image"),
        media_info.get("preview_image"),
    ]
    return [url for url in candidates if isinstance(url, str) and url.startswith("http")]


def extract_status_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        for key in ("list", "statuses"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    for key in ("list", "statuses"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def next_page_from_payload(payload: dict[str, Any], current_page: int, item_count: int) -> str | None:
    data = payload.get("data") if isinstance(payload, dict) else None
    total = data.get("total") if isinstance(data, dict) else None
    if isinstance(total, int) and current_page * item_count >= total:
        return None
    return str(current_page + 1) if item_count > 0 else None


def choose_weibo_full_text(item: dict[str, Any], detail_text: str | None = None) -> str:
    list_text = strip_weibo_html(str(item.get("text_raw") or item.get("text") or ""))
    detail = clean_weibo_detail_text(detail_text)
    if detail and len(detail) > len(list_text):
        return detail
    return list_text


def normalize_weibo_status(uid: str, item: dict[str, Any], full_text: str | None = None) -> NormalizedPost:
    platform_post_id = str(item.get("mid") or item.get("id"))
    original_url = weibo_detail_url(uid, item)
    raw_text = choose_weibo_full_text(item, full_text)

    return NormalizedPost(
        platform="weibo",
        platform_post_id=platform_post_id,
        original_url=original_url,
        published_at=parse_weibo_datetime(item.get("created_at")),
        full_text=raw_text,
        image_urls=image_urls_from_status(item),
        video_cover_urls=video_cover_urls_from_status(item),
        source=item.get("source"),
        is_edited=bool(item.get("edit_count") or "已编辑" in str(item.get("text") or "")),
        raw_data=item,
    )


def has_weibo_auth_cookie(storage_state_path: str | Path) -> bool:
    path = Path(storage_state_path)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    cookies = state.get("cookies") or []
    return any(cookie.get("domain", "").endswith("weibo.com") and cookie.get("name") == "SUB" for cookie in cookies)


def parse_weibo_json_body(body: bytes, content_type: str | None = None) -> dict[str, Any]:
    text = decode_weibo_response_body(body, content_type)
    stripped = text.lstrip()
    if stripped.startswith("<"):
        if "新浪通行证" in text or "passport.weibo.com" in text or "login" in text.lower():
            raise RuntimeError("微博登录态已失效或需要新浪通行证验证，请在平台连接页重新上传/刷新 weibo.json")
        raise RuntimeError("Weibo mymblog response is HTML, not JSON")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Weibo mymblog response is not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Weibo mymblog response is not a JSON object")
    return payload


def decode_weibo_response_body(body: bytes, content_type: str | None = None) -> str:
    charset_match = re.search(r"charset=([\w-]+)", content_type or "", flags=re.IGNORECASE)
    charsets = [charset_match.group(1)] if charset_match else []
    charsets.extend(["utf-8", "gb18030"])
    tried: set[str] = set()
    for charset in charsets:
        normalized = charset.lower()
        if normalized in tried:
            continue
        tried.add(normalized)
        try:
            return body.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


async def collect_weibo_posts(options: WeiboCollectOptions) -> PageResult:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=options.headless)
        context = await browser.new_context(
            storage_state=str(options.storage_state_path),
            user_agent=options.user_agent,
            extra_http_headers={"Referer": f"{WEIBO_BASE_URL}/u/{options.uid}"},
        )
        try:
            payload = await fetch_mblog_payload(context, options.uid, options.page_no)
            statuses = extract_status_items(payload)[: options.limit]
            items: list[NormalizedPost] = []
            detail_count = 0

            for index, status in enumerate(statuses):
                detail_text = None
                if is_truncated_status(status) and detail_count < options.detail_fallback_limit:
                    detail_text = await fetch_detail_text(
                        context,
                        weibo_detail_url(options.uid, status),
                        timeout_ms=options.detail_timeout_ms,
                    )
                    detail_count += 1
                items.append(normalize_weibo_status(options.uid, status, full_text=detail_text))

            return PageResult(
                items=items,
                next_cursor=next_page_from_payload(payload, options.page_no, len(statuses)),
            )
        finally:
            await context.close()
            await browser.close()


async def fetch_mblog_payload(
    context: BrowserContext,
    uid: str,
    page_no: int,
) -> dict[str, Any]:
    response = await context.request.get(
        WEIBO_MBLOG_ENDPOINT,
        params={"uid": uid, "page": str(page_no), "feature": "0"},
        timeout=60000,
    )
    if not response.ok:
        raise RuntimeError(f"Weibo mymblog request failed: HTTP {response.status}")
    body = await response.body()
    return parse_weibo_json_body(body, response.headers.get("content-type"))


async def fetch_detail_text(context: BrowserContext, url: str, *, timeout_ms: int = 10000) -> str | None:
    page = await context.new_page()
    try:
        page.set_default_timeout(timeout_ms)
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(min(1000, max(250, timeout_ms // 10)))
        await click_expand(page)
        return await extract_best_article_text(page)
    except Exception:
        return None
    finally:
        await page.close()


async def click_expand(page: Page) -> None:
    for _ in range(3):
        locator = page.locator("text=展开")
        count = await locator.count()
        if count == 0:
            return
        clicked = False
        for index in range(min(count, 10)):
            item = locator.nth(index)
            try:
                if await item.is_visible(timeout=500):
                    await item.click(timeout=1000)
                    await page.wait_for_timeout(250)
                    clicked = True
            except Exception:
                continue
        if not clicked:
            return


async def extract_best_article_text(page: Page) -> str:
    text = await page.evaluate(
        """
        () => {
          const blocks = Array.from(document.querySelectorAll('article, [role="article"], [class*="detail"], [class*="Detail"]'));
          const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const texts = blocks.map((node) => clean(node.innerText)).filter((text) => text.length > 20);
          texts.sort((a, b) => b.length - a.length);
          return texts[0] || clean(document.body.innerText);
        }
        """
    )
    return strip_weibo_html(text)


class WeiboAdapter(PlatformAdapter):
    platform = "weibo"

    def __init__(
        self,
        storage_state_path: str | Path,
        *,
        headless: bool = True,
        detail_fallback_limit: int = 3,
        detail_timeout_ms: int = 10000,
    ) -> None:
        self.storage_state_path = Path(storage_state_path)
        self.headless = headless
        self.detail_fallback_limit = detail_fallback_limit
        self.detail_timeout_ms = detail_timeout_ms

    async def check_login(self) -> bool:
        if not self.storage_state_path.exists():
            return False
        if not has_weibo_auth_cookie(self.storage_state_path):
            return False
        async with async_playwright() as p:
            request = await p.request.new_context(
                storage_state=str(self.storage_state_path),
                user_agent=DEFAULT_USER_AGENT,
                extra_http_headers={"Referer": WEIBO_BASE_URL},
            )
            try:
                response = await request.get(f"{WEIBO_BASE_URL}/ajax/feed/allGroups", timeout=30000)
                return response.ok
            finally:
                await request.dispose()

    async def fetch_recent_posts(self, account_id: str, limit: int = 20) -> PageResult:
        return await self.fetch_history_page(account_id=account_id, cursor="1", limit=limit)

    async def fetch_history_page(
        self,
        account_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> PageResult:
        page_no = int(cursor or "1")
        return await collect_weibo_posts(
            WeiboCollectOptions(
                storage_state_path=self.storage_state_path,
                uid=account_id,
                page_no=page_no,
                limit=limit,
                headless=self.headless,
                detail_fallback_limit=0,
                detail_timeout_ms=self.detail_timeout_ms,
            )
        )

    def should_fetch_detail_for_monitor(self, post: NormalizedPost, *, is_new: bool) -> bool:
        return is_new or is_truncated_status(post.raw_data)

    async def enrich_posts_with_details(
        self,
        account_id: str,
        posts: list[NormalizedPost],
        *,
        max_count: int,
    ) -> list[NormalizedPost]:
        if max_count <= 0 or not posts:
            return posts

        candidates = posts[:max_count]
        enriched_by_id: dict[str, NormalizedPost] = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                storage_state=str(self.storage_state_path),
                user_agent=DEFAULT_USER_AGENT,
                extra_http_headers={"Referer": f"{WEIBO_BASE_URL}/u/{account_id}"},
            )
            try:
                for post in candidates:
                    detail_text = await fetch_detail_text(
                        context,
                        post.original_url,
                        timeout_ms=self.detail_timeout_ms,
                    )
                    full_text = choose_weibo_full_text(post.raw_data, detail_text)
                    if full_text != (post.full_text or ""):
                        enriched_by_id[post.platform_post_id] = replace(post, full_text=full_text)
            finally:
                await context.close()
                await browser.close()

        return [enriched_by_id.get(post.platform_post_id, post) for post in posts]
