from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp
from sqlalchemy.orm import Session

from app.models import NotificationEvent, SystemSetting

logger = logging.getLogger(__name__)


class NotifierService:
    """Sends notifications via Feishu (Lark) and WeCom (企业微信) webhook bots."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def send_event(
        self,
        event_type: str,
        title: str,
        *,
        platform: str | None = None,
        body: str | None = None,
        reference_id: str | None = None,
        reference_type: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> NotificationEvent:
        """Create a notification event and attempt to send it."""
        channel = self._get_channel()
        event = NotificationEvent(
            event_type=event_type,
            platform=platform,
            channel=channel,
            title=title,
            body=body,
            reference_id=reference_id,
            reference_type=reference_type,
            payload=payload or {},
            status="pending",
        )
        self._db.add(event)
        self._db.flush()

        success = self._try_send(event)
        if success:
            event.status = "sent"
            event.sent_at = datetime.now(timezone.utc)
        else:
            event.status = "failed"
        self._db.commit()
        return event

    def _try_send(self, event: NotificationEvent) -> bool:
        webhook_url = self._get_webhook_url(event.channel)
        if not webhook_url:
            event.error_message = f"No webhook URL configured for {event.channel}"
            return False
        try:
            return asyncio.run(self._async_send(webhook_url, event))
        except Exception as exc:
            logger.exception("Notification send failed")
            event.error_message = str(exc)[:500]
            return False

    async def _async_send(self, webhook_url: str, event: NotificationEvent) -> bool:
        if event.channel == "feishu":
            payload = self._build_feishu_message(event)
        elif event.channel == "wecom":
            payload = self._build_wecom_message(event)
        else:
            return False

        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status in (200, 204):
                    return True
                text = await response.text()
                event.error_message = f"HTTP {response.status}: {text[:400]}"
                return response.status < 500

    def _build_feishu_message(self, event: NotificationEvent) -> dict:
        elements: list[dict] = []
        if event.body:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": event.body}})
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": event.title},
                    "template": "blue",
                },
                "elements": elements,
            },
        }

    def _build_wecom_message(self, event: NotificationEvent) -> dict:
        content = event.title
        if event.body:
            content += f"\n{event.body}"
        return {"msgtype": "text", "text": {"content": content}}

    def _get_channel(self) -> str:
        setting = self._db.query(SystemSetting).filter(SystemSetting.key == "notification_channel").first()
        return (setting.value if setting and setting.value else "feishu").strip()

    def _get_webhook_url(self, channel: str) -> str | None:
        key = f"webhook_{channel}_url"
        setting = self._db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting and setting.value:
            return setting.value.strip()
        return None
