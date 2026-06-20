from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import ImportJob, PlatformAccount
from app.schemas.accounts import (
    AccountCreateRequest,
    AccountPage,
    AccountUpdateRequest,
    PlatformAccountOut,
)
from app.schemas.common import Pagination, SuccessResponse, TaskAcceptedResponse
from app.services.platform.weibo import extract_weibo_uid
from app.services.platform.xueqiu import extract_xueqiu_uid
from app.workers.import_tasks import run_import_job
from app.workers.monitor_tasks import check_account

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("", response_model=AccountPage)
def list_accounts(
    platform: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AccountPage:
    q = db.query(PlatformAccount)
    if platform:
        q = q.filter(PlatformAccount.platform == platform)
    if keyword:
        q = q.filter(PlatformAccount.account_name.ilike(f"%{keyword}%"))
    if status:
        q = q.filter(PlatformAccount.status == status)
    total = q.count()
    items = [PlatformAccountOut.model_validate(row) for row in q.order_by(PlatformAccount.id.desc()).offset((page - 1) * page_size).limit(page_size).all()]
    return AccountPage(items=items, pagination=Pagination(page=page, page_size=page_size, total=total))


@router.post("", response_model=PlatformAccountOut, status_code=201)
def create_account(payload: AccountCreateRequest, db: Session = Depends(get_db)) -> PlatformAccountOut:
    data = payload.model_dump()
    data["platform_account_id"] = _resolve_account_platform_id(
        data["platform"],
        data["profile_url"],
        data.get("platform_account_id"),
    )

    account = PlatformAccount(**data)
    db.add(account)
    db.commit()
    db.refresh(account)
    return PlatformAccountOut.model_validate(account)


@router.get("/{account_id}", response_model=PlatformAccountOut)
def get_account(account_id: int, db: Session = Depends(get_db)) -> PlatformAccountOut:
    account = db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="博主不存在")
    return PlatformAccountOut.model_validate(account)


@router.put("/{account_id}", response_model=PlatformAccountOut)
def update_account(account_id: int, payload: AccountUpdateRequest, db: Session = Depends(get_db)) -> PlatformAccountOut:
    account = db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="博主不存在")
    data = payload.model_dump(exclude_unset=True)
    if "profile_url" in data or "platform_account_id" in data:
        next_profile_url = data.get("profile_url", account.profile_url)
        provided_account_id = data.get("platform_account_id")
        if provided_account_id == "":
            provided_account_id = None
        if "profile_url" in data and provided_account_id == account.platform_account_id:
            provided_account_id = None
        data["platform_account_id"] = _resolve_account_platform_id(
            account.platform,
            next_profile_url,
            provided_account_id,
        )
        account.status = "normal"
        account.error_message = None

    for field, value in data.items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return PlatformAccountOut.model_validate(account)


def _resolve_account_platform_id(platform: str, profile_url: str, platform_account_id: str | None) -> str:
    if platform == "weibo":
        uid = platform_account_id or extract_weibo_uid(profile_url)
        if uid is None:
            raise HTTPException(status_code=400, detail="无法从微博主页 URL 提取 uid，请手动填写 platform_account_id")
        return uid
    if platform == "xueqiu":
        uid = platform_account_id or extract_xueqiu_uid(profile_url)
        if uid is None:
            raise HTTPException(status_code=400, detail="无法从雪球主页 URL 提取用户 ID，请手动填写 platform_account_id")
        return uid
    raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")


@router.delete("/{account_id}", response_model=SuccessResponse)
def delete_account(account_id: int, db: Session = Depends(get_db)) -> SuccessResponse:
    account = db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="博主不存在")
    db.delete(account)
    db.commit()
    return SuccessResponse(message="博主已删除")


@router.post("/{account_id}/enable", response_model=PlatformAccountOut)
def enable_account(account_id: int, db: Session = Depends(get_db)) -> PlatformAccountOut:
    account = db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="博主不存在")
    account.is_enabled = True
    account.status = "normal"
    db.commit()
    db.refresh(account)
    return PlatformAccountOut.model_validate(account)


@router.post("/{account_id}/disable", response_model=PlatformAccountOut)
def disable_account(account_id: int, db: Session = Depends(get_db)) -> PlatformAccountOut:
    account = db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="博主不存在")
    account.is_enabled = False
    account.status = "disabled"
    db.commit()
    db.refresh(account)
    return PlatformAccountOut.model_validate(account)


@router.post("/{account_id}/check-now", response_model=TaskAcceptedResponse)
def check_now(account_id: int, db: Session = Depends(get_db)) -> TaskAcceptedResponse:
    account = db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="博主不存在")
    try:
        task = check_account.delay(account.id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"提交立即检查任务失败：{exc}") from exc
    return TaskAcceptedResponse(
        task_id=task.id,
        message=f"已提交 {account.account_name} 的立即检查任务",
    )


@router.post("/{account_id}/reimport", response_model=TaskAcceptedResponse)
def reimport_account(account_id: int, db: Session = Depends(get_db)) -> TaskAcceptedResponse:
    account = db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="博主不存在")
    if account.init_mode == "none":
        raise HTTPException(status_code=400, detail="当前博主初始化导入模式为 none")

    job = ImportJob(
        account_id=account.id,
        platform=account.platform,
        account_name=account.account_name,
        init_mode=account.init_mode,
        init_limit=account.init_limit,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        task = run_import_job.delay(job.id)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=503, detail=f"提交导入任务失败：{exc}") from exc

    return TaskAcceptedResponse(
        task_id=task.id,
        message=f"已提交 {account.account_name} 的历史导入任务",
    )
