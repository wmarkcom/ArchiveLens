from app.db.session import SessionLocal
from app.models import NotificationEvent
from app.services.notifier import NotifierService
from app.workers.celery_app import celery_app


@celery_app.task(name="notifications.resend")
def resend_notification_event(event_id: int) -> dict:
    db = SessionLocal()
    try:
        event = db.query(NotificationEvent).filter(NotificationEvent.id == event_id).first()
        if event is None:
            return {"event_id": event_id, "status": "not_found"}
        event = NotifierService(db).resend_event(event)
        return {
            "event_id": event.id,
            "status": event.status,
            "error": event.error_message,
        }
    finally:
        db.close()
