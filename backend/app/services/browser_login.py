from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PlatformConnection, PlatformLoginSession
from app.services.platform.weibo import WEIBO_MBLOG_ENDPOINT, parse_weibo_json_body


LOGIN_TTL_MINUTES = 10
WEIBO_LOGIN_URL = "https://weibo.com/login.php"


@dataclass
class BrowserLoginRuntime:
    platform: str
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page
    expires_at: datetime
    screenshot_path: Path


_active_sessions: dict[str, BrowserLoginRuntime] = {}
_session_lock = asyncio.Lock()


async def start_browser_login(db: Session, session: PlatformLoginSession) -> None:
    if session.platform != "weibo":
        raise ValueError("暂只支持微博扫码登录")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=LOGIN_TTL_MINUTES)
    screenshot_path = _screenshot_path(session.id)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Apple Silicon Mac OS X 15_0) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto(WEIBO_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1500)
        await click_weibo_login_entry(page)
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        await playwright.stop()
        raise

    runtime = BrowserLoginRuntime(
        platform=session.platform,
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
        expires_at=expires_at,
        screenshot_path=screenshot_path,
    )
    async with _session_lock:
        old_runtime = _active_sessions.pop(session.id, None)
        _active_sessions[session.id] = runtime
    if old_runtime is not None:
        await close_runtime(old_runtime)

    session.status = "opened"
    session.login_url = WEIBO_LOGIN_URL
    session.expires_at = expires_at
    session.callback_payload = {
        "screenshot_url": login_screenshot_url(session.platform, session.id),
        "message": "请用微博 App 扫描截图中的二维码，并在手机上确认登录",
    }
    session.error_message = None
    db.commit()


async def refresh_browser_login(db: Session, session: PlatformLoginSession) -> PlatformLoginSession:
    runtime = _active_sessions.get(session.id)
    now = datetime.now(timezone.utc)

    if session.status in {"success", "failed", "expired"}:
        return session

    if runtime is None:
        session.status = "failed"
        session.error_message = "登录浏览器会话不存在或服务已重启，请重新发起扫码登录"
        session.finished_at = now
        db.commit()
        return session

    if now >= runtime.expires_at:
        session.status = "expired"
        session.error_message = "扫码登录已超时，请重新发起登录"
        session.finished_at = now
        db.commit()
        await cleanup_browser_login(session.id)
        return session

    cookies = await runtime.context.cookies()
    if _has_required_cookie(session.platform, cookies):
        auth_path = settings.platform_auth_state_path(session.platform)
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        state = await runtime.context.storage_state()
        try:
            await _validate_platform_state(session.platform, state)
        except Exception as exc:
            session.status = "failed"
            session.finished_at = now
            session.error_message = str(exc)[:500]
            session.callback_payload = {
                **(session.callback_payload or {}),
                "message": "扫码登录拿到了 cookie，但微博采集接口仍不可用，未覆盖现有登录态",
            }
            db.commit()
            await cleanup_browser_login(session.id)
            return session
        _write_storage_state(auth_path, state)

        connection = _get_or_create_connection(db, session.platform)
        connection.status = "connected"
        connection.session_data_encrypted = auth_path.name
        connection.last_login_at = now
        connection.error_message = None

        session.status = "success"
        session.finished_at = now
        session.error_message = None
        session.callback_payload = {
            **(session.callback_payload or {}),
            "message": "扫码登录成功，登录态已保存",
        }
        db.commit()
        await cleanup_browser_login(session.id)
        return session

    try:
        await runtime.page.screenshot(path=str(runtime.screenshot_path), full_page=True)
    except Exception:
        pass

    session.status = "opened"
    session.callback_payload = {
        **(session.callback_payload or {}),
        "screenshot_url": login_screenshot_url(session.platform, session.id),
        "message": "等待扫码确认中",
    }
    db.commit()
    return session


async def click_browser_login_action(
    db: Session,
    session: PlatformLoginSession,
    payload: dict[str, Any],
) -> PlatformLoginSession:
    runtime = _active_sessions.get(session.id)
    now = datetime.now(timezone.utc)

    if session.status in {"success", "failed", "expired"}:
        return session
    if runtime is None:
        session.status = "failed"
        session.error_message = "登录浏览器会话不存在或服务已重启，请重新发起扫码登录"
        session.finished_at = now
        db.commit()
        return session
    action = str(payload.get("action") or "")
    if action != "open_login":
        if action != "click":
            session.error_message = f"不支持的登录动作：{action}"
            db.commit()
            return session
        await click_page_coordinates(runtime.page, payload)
    else:
        await click_weibo_login_entry(runtime.page)
    await runtime.page.wait_for_timeout(1000)
    await runtime.page.screenshot(path=str(runtime.screenshot_path), full_page=True)
    session.callback_payload = {
        **(session.callback_payload or {}),
        "screenshot_url": login_screenshot_url(session.platform, session.id),
        "message": "已在服务器浏览器执行点击，请继续操作或扫码确认",
    }
    db.commit()
    return session


async def cleanup_browser_login(session_id: str) -> None:
    async with _session_lock:
        runtime = _active_sessions.pop(session_id, None)
    if runtime is not None:
        await close_runtime(runtime)


async def close_runtime(runtime: BrowserLoginRuntime) -> None:
    try:
        await runtime.context.close()
    finally:
        try:
            await runtime.browser.close()
        finally:
            await runtime.playwright.stop()


async def click_weibo_login_entry(page: Page) -> None:
    candidates = [
        "text=登录/注册",
        "text=登录",
        "a:has-text('登录')",
        "button:has-text('登录')",
        "[node-type='loginBtn']",
        ".loginBtn",
    ]
    for selector in candidates:
        try:
            locator = page.locator(selector).first
            if await locator.is_visible(timeout=1200):
                await locator.click(timeout=2000)
                await page.wait_for_timeout(1500)
                return
        except Exception:
            continue


async def click_page_coordinates(page: Page, payload: dict[str, Any]) -> None:
    x = float(payload.get("x", 0))
    y = float(payload.get("y", 0))
    if x < 0 or y < 0:
        raise ValueError("点击坐标无效")

    viewport = page.viewport_size or {"width": 1280, "height": 900}
    viewport_width = float(viewport["width"])
    viewport_height = float(viewport["height"])
    page_height = await page.evaluate("() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    scroll_y = max(0, min(y - viewport_height / 2, float(page_height) - viewport_height))
    await page.evaluate("(scrollY) => window.scrollTo(0, scrollY)", scroll_y)
    await page.wait_for_timeout(150)
    click_x = max(0, min(x, viewport_width - 1))
    click_y = max(0, min(y - scroll_y, viewport_height - 1))
    await page.mouse.click(click_x, click_y)


def login_screenshot_path(platform: str, session_id: str) -> Path:
    path = _screenshot_path(session_id)
    if platform != "weibo":
        raise ValueError("暂只支持微博扫码登录")
    return path


def login_screenshot_url(platform: str, session_id: str) -> str:
    return f"/connections/{platform}/login/{session_id}/screenshot"


def login_session_payload(session: PlatformLoginSession) -> dict[str, Any]:
    payload = session.callback_payload or {}
    return {
        "id": session.id,
        "platform": session.platform,
        "status": session.status,
        "login_url": session.login_url,
        "expires_at": session.expires_at,
        "screenshot_url": payload.get("screenshot_url"),
        "message": payload.get("message"),
        "error_message": session.error_message,
    }


def _screenshot_path(session_id: str) -> Path:
    return Path(settings.auth_root) / "login_sessions" / f"{session_id}.png"


def _has_required_cookie(platform: str, cookies: list[dict[str, Any]]) -> bool:
    if platform == "weibo":
        return any(cookie.get("domain", "").endswith("weibo.com") and cookie.get("name") == "SUB" for cookie in cookies)
    if platform == "xueqiu":
        return any(cookie.get("domain", "").endswith("xueqiu.com") for cookie in cookies)
    return bool(cookies)


async def _validate_platform_state(platform: str, state: dict[str, Any]) -> None:
    if platform != "weibo":
        return
    playwright = await async_playwright().start()
    request = await playwright.request.new_context(
        storage_state=state,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Apple Silicon Mac OS X 15_0) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        extra_http_headers={
            "Referer": "https://weibo.com/u/1002568141",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    try:
        response = await request.get(
            WEIBO_MBLOG_ENDPOINT,
            params={"uid": "1002568141", "page": "1", "feature": "0"},
            timeout=30000,
        )
        body = await response.body()
        if not response.ok:
            try:
                payload = parse_weibo_json_body(body, response.headers.get("content-type"))
                message = payload.get("message") if isinstance(payload, dict) else None
            except Exception:
                message = None
            detail = f"：{message}" if message else ""
            raise RuntimeError(f"微博登录态尚不可用于采集接口，HTTP {response.status}{detail}")
        parse_weibo_json_body(body, response.headers.get("content-type"))
    finally:
        await request.dispose()
        await playwright.stop()


def _write_storage_state(path: Path, state: dict[str, Any]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as temp_file:
        json.dump(state, temp_file, ensure_ascii=False, indent=2)
        temp_name = temp_file.name
    os.replace(temp_name, path)


def _get_or_create_connection(db: Session, platform: str) -> PlatformConnection:
    conn = db.query(PlatformConnection).filter(PlatformConnection.platform == platform).first()
    if conn is None:
        conn = PlatformConnection(platform=platform)
        db.add(conn)
        db.flush()
    return conn
