from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from app.core.config import settings
from app.models import MediaAsset
from app.schemas.media import MediaAssetOut

MEDIA_FILES_PREFIX = "/media-files"


def media_local_url(local_path: str | None) -> str | None:
    if not local_path:
        return None

    media_root = Path(settings.media_root).resolve()
    path = Path(local_path).resolve()
    if not path.is_file():
        return None

    try:
        relative = path.relative_to(media_root)
    except ValueError:
        return None

    return f"{MEDIA_FILES_PREFIX}/{quote(relative.as_posix(), safe='/')}"


def media_asset_to_out(asset: MediaAsset) -> MediaAssetOut:
    return MediaAssetOut.model_validate(asset).model_copy(
        update={"local_url": media_local_url(asset.local_path)}
    )


def media_asset_preview_url(asset: MediaAsset | None) -> str | None:
    if asset is None:
        return None
    return media_local_url(asset.local_path) or asset.original_url
