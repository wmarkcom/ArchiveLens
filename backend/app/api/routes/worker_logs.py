from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import WorkerRunLog
from app.schemas.common import Pagination
from app.schemas.worker_logs import WorkerRunLogOut, WorkerRunLogPage

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("", response_model=WorkerRunLogPage)
def list_worker_logs(
    worker_name: str | None = Query(default=None),
    task_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> WorkerRunLogPage:
    q = db.query(WorkerRunLog)
    if worker_name:
        q = q.filter(WorkerRunLog.worker_name == worker_name)
    if task_name:
        q = q.filter(WorkerRunLog.task_name == task_name)
    if status:
        q = q.filter(WorkerRunLog.status == status)

    total = q.count()
    rows = (
        q.order_by(WorkerRunLog.started_at.desc(), WorkerRunLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return WorkerRunLogPage(
        items=[WorkerRunLogOut.model_validate(row) for row in rows],
        pagination=Pagination(page=page, page_size=page_size, total=total),
    )
