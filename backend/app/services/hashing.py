import hashlib
import json
from typing import Any


def compute_content_hash(
    platform: str,
    platform_post_id: str,
    full_text: str | None = None,
    repost_text: str | None = None,
    image_urls: list[str] | None = None,
    title: str | None = None,
) -> str:
    """Compute a stable content hash for deduplication and edit detection.

    The hash covers the fields that materially define post content —
    if any of them changes, the hash changes, which triggers a new snapshot.
    """
    payload: dict[str, Any] = {
        "platform": platform,
        "platform_post_id": platform_post_id,
        "title": title or "",
        "full_text": full_text or "",
        "repost_text": repost_text or "",
        "image_urls": sorted(image_urls or []),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
