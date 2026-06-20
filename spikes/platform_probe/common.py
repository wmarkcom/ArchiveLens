from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from playwright.sync_api import Page, Response, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
AUTH_DIR = ROOT / "auth"
OUTPUT_DIR = ROOT / "spikes" / "platform_probe" / "output"


def auth_state_path(platform: str) -> Path:
    return AUTH_DIR / f"{platform}.json"


def ensure_dirs() -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def login_and_save(platform: str, login_url: str) -> None:
    ensure_dirs()
    storage_path = auth_state_path(platform)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=60000)

        print(f"已打开 {platform} 登录页。")
        print("请在浏览器中手动完成登录。登录成功后回到终端按 Enter 保存 session。")
        input()

        context.storage_state(path=str(storage_path))
        print(f"session 已保存：{storage_path}")
        browser.close()


def build_arg_parser(platform: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Probe {platform} profile page")
    parser.add_argument("profile_url", help="Target profile URL")
    parser.add_argument("--scrolls", type=int, default=4, help="Number of page scrolls")
    parser.add_argument("--wait-ms", type=int, default=1500, help="Wait after each scroll")
    parser.add_argument("--max-json", type=int, default=40, help="Max JSON responses to capture")
    parser.add_argument("--download-images", type=int, default=12, help="Max candidate images to download")
    parser.add_argument("--detail-pages", type=int, default=5, help="Max post detail pages to inspect")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    return parser


def summarize_value(value: Any, max_text: int = 800) -> Any:
    if isinstance(value, str):
        text = re.sub(r"\s+", " ", value).strip()
        return text[:max_text]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [summarize_value(item, max_text=max_text) for item in value[:5]]
    if isinstance(value, dict):
        selected: dict[str, Any] = {}
        for key in (
            "id",
            "mid",
            "status_id",
            "created_at",
            "title",
            "text",
            "text_raw",
            "content",
            "description",
            "source",
            "pic",
            "pic_ids",
            "pics",
            "url",
            "target",
        ):
            if key in value:
                selected[key] = summarize_value(value[key], max_text=max_text)
        return selected or {k: summarize_value(v, max_text=max_text) for k, v in list(value.items())[:8]}
    return str(value)[:max_text]


def looks_like_post_dict(value: dict[str, Any]) -> bool:
    id_keys = {"id", "mid", "status_id", "target", "url"}
    text_keys = {"text", "text_raw", "content", "description", "title"}
    return bool(id_keys.intersection(value.keys()) and text_keys.intersection(value.keys()))


def collect_candidate_dicts(value: Any, found: list[dict[str, Any]], limit: int = 30) -> None:
    if len(found) >= limit:
        return
    if isinstance(value, dict):
        if looks_like_post_dict(value):
            found.append(summarize_value(value))
        for child in value.values():
            collect_candidate_dicts(child, found, limit=limit)
    elif isinstance(value, list):
        for item in value:
            collect_candidate_dicts(item, found, limit=limit)
            if len(found) >= limit:
                break


def capture_json_response(response: Response, captured: list[dict[str, Any]], max_json: int) -> None:
    if len(captured) >= max_json:
        return

    content_type = response.headers.get("content-type", "")
    url = response.url
    interesting_url = any(token in url.lower() for token in ("api", "ajax", "status", "timeline", "profile"))
    if "json" not in content_type.lower() and not interesting_url:
        return

    try:
        payload = response.json()
    except Exception:
        return

    candidates: list[dict[str, Any]] = []
    collect_candidate_dicts(payload, candidates)
    captured.append(
        {
            "url": url,
            "status": response.status,
            "content_type": content_type,
            "candidate_count": len(candidates),
            "candidates": candidates[:10],
            "summary": summarize_value(payload, max_text=500),
        }
    )


def extract_dom(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const trim = (value, length = 1200) =>
            (value || '').replace(/\\s+/g, ' ').trim().slice(0, length);

          const blockSelectors = [
            'article',
            '[role="article"]',
            '[class*="Feed"]',
            '[class*="feed"]',
            '[class*="card"]',
            '[class*="Card"]',
            '[class*="status"]',
            '[class*="Status"]',
            '[class*="timeline"]',
            '[class*="Timeline"]'
          ];

          const seen = new Set();
          const candidates = [];

          for (const selector of blockSelectors) {
            for (const element of document.querySelectorAll(selector)) {
              if (seen.has(element)) continue;
              seen.add(element);
              const text = trim(element.innerText, 1600);
              if (text.length < 20) continue;
              candidates.push({
                selector,
                id: element.id || null,
                className: String(element.className || '').slice(0, 240),
                text,
                links: Array.from(element.querySelectorAll('a')).slice(0, 10).map((a) => ({
                  text: trim(a.innerText, 100),
                  href: a.href
                })),
                images: Array.from(element.querySelectorAll('img')).slice(0, 10).map((img) => ({
                  src: img.currentSrc || img.src,
                  alt: img.alt || '',
                  width: img.naturalWidth || img.width || 0,
                  height: img.naturalHeight || img.height || 0
                })).filter((item) => item.src)
              });
              if (candidates.length >= 40) break;
            }
            if (candidates.length >= 40) break;
          }

          return {
            title: document.title,
            url: location.href,
            body_text_sample: trim(document.body.innerText, 3000),
            links: Array.from(document.links).slice(0, 200).map((a) => ({
              text: trim(a.innerText, 100),
              href: a.href
            })).filter((item) => item.href),
            images: Array.from(document.images).slice(0, 200).map((img) => ({
              src: img.currentSrc || img.src,
              alt: img.alt || '',
              width: img.naturalWidth || img.width || 0,
              height: img.naturalHeight || img.height || 0
            })).filter((item) => item.src),
            candidates
          };
        }
        """
    )


def is_likely_post_image(image: dict[str, Any]) -> bool:
    src = str(image.get("src") or "")
    if not src.startswith("http"):
        return False
    host = urlparse(src).netloc.lower()
    if "sinaimg.cn" not in host:
        return False
    if host.startswith("tva") or host.startswith("tvax"):
        return False
    if "/upload/" in src or "vvip" in src.lower():
        return False
    width = int(image.get("width") or 0)
    height = int(image.get("height") or 0)
    return width >= 120 and height >= 120


def normalize_weibo_image_url(url: str) -> str:
    # orj360/orj480 are display thumbnails; mw2000 is closer to an archive-quality source.
    return re.sub(r"/orj\d+/", "/mw2000/", url)


def image_extension(content_type: str, url: str) -> str:
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def collect_post_images(dom: dict[str, Any], max_images: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    images: list[dict[str, Any]] = []
    for candidate in dom.get("candidates", []):
        text = str(candidate.get("text") or "")
        for image in candidate.get("images", []):
            if not is_likely_post_image(image):
                continue
            src = normalize_weibo_image_url(str(image["src"]))
            if src in seen:
                continue
            seen.add(src)
            images.append(
                {
                    "url": src,
                    "source_text": text[:160],
                    "width": image.get("width"),
                    "height": image.get("height"),
                }
            )
            if len(images) >= max_images:
                return images
    return images


def collect_detail_links(dom: dict[str, Any], max_links: int) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for candidate in dom.get("candidates", []):
        for link in candidate.get("links", []):
            href = str(link.get("href") or "")
            text = str(link.get("text") or "")
            if not href.startswith("https://weibo.com/"):
                continue
            if "/u/" in href or "/n/" in href:
                continue
            if not text or text.startswith("#") or text.startswith("@"):
                continue
            if href in seen:
                continue
            seen.add(href)
            links.append(href)
            if len(links) >= max_links:
                return links
    return links


def inspect_detail_pages(context: Any, links: list[str], wait_ms: int) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for link in links:
        page = context.new_page()
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(wait_ms)
            expand_clicks = click_expand_buttons(page, rounds=5)
            page.wait_for_timeout(500)
            dom = extract_dom(page)
            best_text = ""
            best_images: list[dict[str, Any]] = []
            for candidate in dom.get("candidates", []):
                text = str(candidate.get("text") or "")
                if len(text) > len(best_text):
                    best_text = text
                    best_images = candidate.get("images", [])
            details.append(
                {
                    "url": link,
                    "title": dom.get("title"),
                    "expand_clicks": expand_clicks,
                    "text": best_text,
                    "images": best_images,
                }
            )
        except Exception as exc:
            details.append({"url": link, "error": str(exc)})
        finally:
            page.close()
    return details


def click_expand_buttons(page: Page, rounds: int = 3) -> int:
    clicked = 0
    for _ in range(rounds):
        count = page.locator("text=展开").count()
        if count == 0:
            break
        did_click = False
        for index in range(min(count, 20)):
            item = page.locator("text=展开").nth(index)
            try:
                if item.is_visible(timeout=500):
                    item.click(timeout=1000)
                    page.wait_for_timeout(250)
                    clicked += 1
                    did_click = True
            except Exception:
                continue
        if not did_click:
            break
    return clicked


def download_candidate_images(
    context: Any,
    run_id: str,
    images: list[dict[str, Any]],
    referer: str,
    user_agent: str,
) -> list[dict[str, Any]]:
    media_dir = OUTPUT_DIR / f"{run_id}_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[dict[str, Any]] = []

    for index, image in enumerate(images, start=1):
        url = image["url"]
        item = dict(image)
        try:
            response = context.request.get(
                url,
                timeout=30000,
                headers={
                    "Referer": referer,
                    "User-Agent": user_agent,
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
            content_type = response.headers.get("content-type", "")
            if not response.ok:
                item["download_status"] = "failed"
                item["error"] = f"HTTP {response.status}"
            else:
                ext = image_extension(content_type, url)
                local_path = media_dir / f"image_{index:02d}{ext}"
                local_path.write_bytes(response.body())
                item["download_status"] = "success"
                item["content_type"] = content_type
                item["local_path"] = str(local_path.relative_to(ROOT))
                item["file_size"] = local_path.stat().st_size
        except Exception as exc:
            item["download_status"] = "failed"
            item["error"] = str(exc)
        downloaded.append(item)

    return downloaded


def run_probe(
    platform: str,
    profile_url: str,
    scrolls: int,
    wait_ms: int,
    max_json: int,
    headless: bool,
    download_images: int,
    detail_pages: int,
) -> Path:
    ensure_dirs()
    storage_path = auth_state_path(platform)
    if not storage_path.exists():
        raise SystemExit(f"缺少登录态文件：{storage_path}。请先运行 login_{platform}.py。")

    run_id = f"{platform}_{timestamp()}"
    json_responses: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=str(storage_path),
            viewport={"width": 1440, "height": 1000},
        )
        page = context.new_page()
        page.on("response", lambda response: capture_json_response(response, json_responses, max_json))

        page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        expand_clicks = click_expand_buttons(page)

        for _ in range(scrolls):
            page.mouse.wheel(0, 1800)
            page.wait_for_timeout(wait_ms)
            expand_clicks += click_expand_buttons(page, rounds=1)

        dom = extract_dom(page)
        screenshot_path = OUTPUT_DIR / f"{run_id}.png"
        page.screenshot(path=str(screenshot_path), full_page=False)

        detail_links = collect_detail_links(dom, detail_pages)
        post_details = inspect_detail_pages(context, detail_links, wait_ms=wait_ms)

        user_agent = page.evaluate("() => navigator.userAgent")
        image_candidates = collect_post_images(dom, download_images)
        downloaded_images = download_candidate_images(
            context=context,
            run_id=run_id,
            images=image_candidates,
            referer=profile_url,
            user_agent=user_agent,
        )

        result = {
            "platform": platform,
            "profile_url": profile_url,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "viewport_screenshot": str(screenshot_path.relative_to(ROOT)),
            "expand_clicks": expand_clicks,
            "detail_links": detail_links,
            "post_details": post_details,
            "downloaded_images": downloaded_images,
            "dom": dom,
            "network_json": json_responses,
            "notes": [
                "优先查看 network_json.candidates，通常比 DOM 更适合后续 adapter。",
                "如果 DOM 有内容但 network_json 为空，后续可先做页面解析。",
                "如果两者都为空，优先确认 session 是否过期、主页 URL 是否正确。",
                "viewport_screenshot 是页面诊断截图；downloaded_images 才是候选正文图片下载结果。",
                "post_details 是逐条打开微博详情页后的候选完整正文，优先用于判断详情页采集可行性。",
            ],
        }

        output_path = OUTPUT_DIR / f"{run_id}.json"
        save_json(output_path, result)
        browser.close()
        return output_path
