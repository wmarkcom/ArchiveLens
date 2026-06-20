from fastapi import APIRouter

from app.api.routes import accounts, connections, dashboard, import_jobs, media, notifications, posts, settings, system, worker_logs

api_router = APIRouter()
api_router.include_router(system.router, tags=["System"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(connections.router, prefix="/connections", tags=["Connections"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
api_router.include_router(posts.router, prefix="/posts", tags=["Posts"])
api_router.include_router(import_jobs.router, prefix="/import-jobs", tags=["ImportJobs"])
api_router.include_router(media.router, prefix="/media", tags=["Media"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(worker_logs.router, prefix="/worker-logs", tags=["WorkerLogs"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
