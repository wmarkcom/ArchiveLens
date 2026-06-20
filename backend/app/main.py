from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.services.media_urls import MEDIA_FILES_PREFIX


def create_app() -> FastAPI:
    app = FastAPI(
        title="ArchiveLens API",
        version="0.1.0",
        default_response_class=settings.default_response_class,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router, prefix="/api")
    media_root = Path(settings.media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    app.mount(MEDIA_FILES_PREFIX, StaticFiles(directory=str(media_root)), name="media-files")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
