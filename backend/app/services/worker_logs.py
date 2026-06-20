from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import WorkerRunLog


def start_worker_run(
    db: Session,
    *,
    worker_name: str,
    task_name: str,
    payload: dict[str, Any] | None = None,
) -> WorkerRunLog:
    log = WorkerRunLog(
        worker_name=worker_name,
        task_name=task_name,
        status="running",
        started_at=datetime.now(timezone.utc),
        payload=payload or {},
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def finish_worker_run(
    db: Session,
    log: WorkerRunLog | None,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    if log is None:
        return

    finished_at = datetime.now(timezone.utc)
    started_at = log.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    log.status = status
    log.finished_at = finished_at
    log.duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
    log.error_message = error_message[:500] if error_message else None
    if result is not None:
        log.payload = {**(log.payload or {}), "result": _json_safe(result)}
    db.commit()


def worker_status_from_result(result: dict[str, Any]) -> str:
    status = str(result.get("status", "")).lower()
    if status in {"failed", "error"}:
        return "failed"
    return "success"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
