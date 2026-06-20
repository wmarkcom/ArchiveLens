from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import MediaAsset

logger = logging.getLogger(__name__)


class MediaDownloader:
    """Downloads media assets to local disk.

    Path convention: /data/media/{platform}/{yyyy}/{mm}/{dd}/post_{platform_post_id}/{type}_{index}.{ext}
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def download_asset(self, asset_id: int) -> dict:
        """Download a single media asset by its ID."""
        asset = self._db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()
        if asset is None:
            return {"asset_id": asset_id, "status": "not_found"}

        try:
            asset.download_status = "downloading"
            asset.retry_count = (asset.retry_count or 0) + 1
            self._db.commit()

            local_path = asyncio.run(self._download_to_local(asset))

            asset.download_status = "success"
            asset.local_path = local_path
            asset.error_message = None
            self._db.commit()

            return {"asset_id": asset_id, "status": "success", "local_path": local_path}
        except Exception as exc:
            logger.exception("Download failed for asset %s", asset_id)
            asset.download_status = "failed"
            asset.error_message = str(exc)[:500]
            self._db.commit()
            return {"asset_id": asset_id, "status": "failed", "error": str(exc)}

    async def _download_to_local(self, asset: MediaAsset) -> str:
        now = asset.created_at or datetime.now(timezone.utc)
        ext = self._guess_extension(asset.original_url)
        directory = (
            Path(settings.media_root)
            / asset.platform
            / now.strftime("%Y")
            / now.strftime("%m")
            / now.strftime("%d")
            / f"post_{asset.platform_post_id}"
        )
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{asset.asset_type}_{asset.sort_order}.{ext}"
        filepath = directory / filename

        async with aiohttp.ClientSession() as session:
            async with session.get(
                asset.original_url,
                timeout=aiohttp.ClientTimeout(total=30),
                headers=self._default_headers(asset.platform),
            ) as response:
                response.raise_for_status()
                content = await response.read()

        filepath.write_bytes(content)

        asset.file_size = len(content)
        if response.content_type:
            asset.mime_type = response.content_type

        return str(filepath)

    @staticmethod
    def _guess_extension(url: str) -> str:
        path = urlparse(url).path
        _, ext = os.path.splitext(path)
        if ext and ext.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
            return ext.lstrip(".")
        return "jpg"

    @staticmethod
    def _default_headers(platform: str) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Apple Silicon Mac OS X 15_0) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": "https://weibo.com" if platform == "weibo" else "https://xueqiu.com",
        }
