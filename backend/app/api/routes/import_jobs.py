from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import ImportJob
from app.schemas.common import Pagination, TaskAcceptedResponse
from app.schemas.import_jobs import ImportJobOut, ImportJobPage
from app.workers.import_tasks import run_import_job

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("", response_model=ImportJobPage)
def list_import_jobs(
    account_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ImportJobPage:
    q = db.query(ImportJob)
    if account_id:
        q = q.filter(ImportJob.account_id == account_id)
    if status:
        q = q.filter(ImportJob.status == status)
    total = q.count()
    rows = q.order_by(ImportJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [ImportJobOut.model_validate(row) for row in rows]
    return ImportJobPage(items=items, pagination=Pagination(page=page, page_size=page_size, total=total))


@router.get("/{job_id}", response_model=ImportJobOut)
def get_import_job(job_id: int, db: Session = Depends(get_db)) -> ImportJobOut:
    job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return ImportJobOut.model_validate(job)


@router.post("/{job_id}/retry", response_model=TaskAcceptedResponse)
def retry_import_job(job_id: int, db: Session = Depends(get_db)) -> TaskAcceptedResponse:
    job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    if job.status not in ("failed", "paused", "cancelled"):
        raise HTTPException(status_code=400, detail="仅失败/暂停/取消的任务可以重试")
    job.status = "pending"
    job.error_message = None
    db.commit()
    try:
        task = run_import_job.delay(job.id)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=503, detail=f"提交导入任务失败：{exc}") from exc
    return TaskAcceptedResponse(task_id=task.id, message="导入任务已重新排队")
