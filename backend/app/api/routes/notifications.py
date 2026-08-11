from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import NotificationEvent
from app.schemas.common import Pagination, SuccessResponse
from app.schemas.notifications import NotificationEventOut, NotificationPage
from app.workers.notification_tasks import resend_notification_event

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("", response_model=NotificationPage)
def list_notifications(
    event_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> NotificationPage:
    q = db.query(NotificationEvent)
    if event_type:
        q = q.filter(NotificationEvent.event_type == event_type)
    if status:
        q = q.filter(NotificationEvent.status == status)
    if channel:
        q = q.filter(NotificationEvent.channel == channel)
    total = q.count()
    rows = q.order_by(NotificationEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [NotificationEventOut.model_validate(row) for row in rows]
    return NotificationPage(items=items, pagination=Pagination(page=page, page_size=page_size, total=total))


@router.get("/{event_id}", response_model=NotificationEventOut)
def get_notification(event_id: int, db: Session = Depends(get_db)) -> NotificationEventOut:
    event = db.query(NotificationEvent).filter(NotificationEvent.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="通知记录不存在")
    return NotificationEventOut.model_validate(event)


@router.post("/{event_id}/resend", response_model=SuccessResponse)
def resend_notification(event_id: int, db: Session = Depends(get_db)) -> SuccessResponse:
    event = db.query(NotificationEvent).filter(NotificationEvent.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="通知记录不存在")
    if event.status != "failed":
        raise HTTPException(status_code=400, detail="仅发送失败的通知可以重发")
    task = resend_notification_event.delay(event_id)
    return SuccessResponse(message=f"通知已重新排队：{task.id}")
