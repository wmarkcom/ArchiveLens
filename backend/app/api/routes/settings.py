from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import SystemSetting
from app.schemas.notifications import NotificationEventOut
from app.schemas.settings import SettingsBulkUpdateRequest, SystemSettingOut
from app.services.notifier import NotifierService

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("", response_model=list[SystemSettingOut])
def list_settings(db: Session = Depends(get_db)) -> list[SystemSettingOut]:
    rows = db.query(SystemSetting).order_by(SystemSetting.key).all()
    return [SystemSettingOut.model_validate(row) for row in rows]


@router.put("", response_model=list[SystemSettingOut])
def update_settings(
    payload: SettingsBulkUpdateRequest,
    db: Session = Depends(get_db),
) -> list[SystemSettingOut]:
    existing = {row.key: row for row in db.query(SystemSetting).all()}
    for item in payload.settings:
        if item.key in existing:
            existing[item.key].value = item.value
        else:
            db.add(SystemSetting(key=item.key, value=item.value, value_type="string"))
    db.commit()
    rows = db.query(SystemSetting).order_by(SystemSetting.key).all()
    return [SystemSettingOut.model_validate(row) for row in rows]


@router.post("/test-notification", response_model=NotificationEventOut)
def test_notification(db: Session = Depends(get_db)) -> NotificationEventOut:
    event = NotifierService(db).send_event(
        event_type="system",
        title="通知测试",
        body="通知链路测试成功。后续健康检查和已开启推送的博主事件会通过当前渠道发送。",
        payload={"test": True},
    )
    return NotificationEventOut.model_validate(event)
