from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlatformConnection(Base):
    __tablename__ = "platform_connections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="disconnected")
    session_data_encrypted: Mapped[str | None] = mapped_column(Text)
    session_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("platform IN ('weibo', 'xueqiu')", name="chk_platform_connections_platform"),
        CheckConstraint(
            "status IN ('disconnected', 'pending_login', 'connected', 'expired', 'failed')",
            name="chk_platform_connections_status",
        ),
        Index("idx_platform_connections_status", "status"),
    )


class PlatformLoginSession(Base):
    __tablename__ = "platform_login_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    login_url: Mapped[str | None] = mapped_column(Text)
    callback_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("platform IN ('weibo', 'xueqiu')", name="chk_platform_login_sessions_platform"),
        CheckConstraint(
            "status IN ('pending', 'opened', 'success', 'failed', 'expired')",
            name="chk_platform_login_sessions_status",
        ),
        Index("idx_platform_login_sessions_platform_status", "platform", "status"),
        Index("idx_platform_login_sessions_expires_at", "expires_at"),
    )


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_url: Mapped[str] = mapped_column(Text, nullable=False)
    platform_account_id: Mapped[str | None] = mapped_column(String(255))
    check_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    init_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="recent")
    init_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_post_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(back_populates="account", lazy="raise")
    import_jobs: Mapped[list["ImportJob"]] = relationship(back_populates="account", lazy="raise")

    __table_args__ = (
        CheckConstraint("platform IN ('weibo', 'xueqiu')", name="chk_platform_accounts_platform"),
        CheckConstraint("init_mode IN ('none', 'recent', 'all')", name="chk_platform_accounts_init_mode"),
        CheckConstraint("status IN ('normal', 'disabled', 'failed')", name="chk_platform_accounts_status"),
        CheckConstraint("check_interval >= 60", name="chk_platform_accounts_check_interval"),
        CheckConstraint("init_limit >= 0", name="chk_platform_accounts_init_limit"),
        Index("uq_platform_accounts_platform_account_id", "platform", "platform_account_id", unique=True,
              postgresql_where=platform_account_id.isnot(None)),
        Index("idx_platform_accounts_platform", "platform"),
        Index("idx_platform_accounts_enabled", "is_enabled"),
        Index("idx_platform_accounts_status", "status"),
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("platform_accounts.id"), nullable=False)
    platform_post_id: Mapped[str] = mapped_column(String(128), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str | None] = mapped_column(String(512))
    full_text: Mapped[str | None] = mapped_column(Text)
    repost_text: Mapped[str | None] = mapped_column(Text)
    image_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    video_cover_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[str | None] = mapped_column(String(128))
    content_hash: Mapped[str | None] = mapped_column(String(128))
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    edit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    error_message: Mapped[str | None] = mapped_column(Text)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[PlatformAccount] = relationship(back_populates="posts", lazy="raise")
    snapshots: Mapped[list["PostSnapshot"]] = relationship(back_populates="post", lazy="raise", order_by="PostSnapshot.version")
    media_assets: Mapped[list["MediaAsset"]] = relationship(back_populates="post", lazy="raise")

    __table_args__ = (
        CheckConstraint("platform IN ('weibo', 'xueqiu')", name="chk_posts_platform"),
        CheckConstraint("status IN ('normal', 'edited', 'deleted', 'hidden', 'failed')", name="chk_posts_status"),
        Index("uq_posts_platform_post_id", "platform", "platform_post_id", unique=True),
        Index("idx_posts_account_id", "account_id"),
        Index("idx_posts_platform", "platform"),
        Index("idx_posts_status", "status"),
        Index("idx_posts_published_at", "published_at"),
        Index("idx_posts_last_collected_at", "last_collected_at"),
    )


class PostSnapshot(Base):
    __tablename__ = "post_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_post_id: Mapped[str] = mapped_column(String(128), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str | None] = mapped_column(String(512))
    full_text: Mapped[str | None] = mapped_column(Text)
    repost_text: Mapped[str | None] = mapped_column(Text)
    image_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    video_cover_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[str | None] = mapped_column(String(128))
    content_hash: Mapped[str | None] = mapped_column(String(128))
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped[Post] = relationship(back_populates="snapshots", lazy="raise")

    __table_args__ = (
        Index("uq_post_snapshots_post_version", "post_id", "version", unique=True),
        Index("idx_post_snapshots_post_id", "post_id"),
        Index("idx_post_snapshots_captured_at", "captured_at"),
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_post_id: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(64))
    download_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    post: Mapped[Post] = relationship(back_populates="media_assets", lazy="raise")

    __table_args__ = (
        CheckConstraint("platform IN ('weibo', 'xueqiu')", name="chk_media_assets_platform"),
        CheckConstraint("asset_type IN ('image', 'video_cover')", name="chk_media_assets_asset_type"),
        CheckConstraint(
            "download_status IN ('pending', 'downloading', 'success', 'failed')",
            name="chk_media_assets_download_status",
        ),
        Index("idx_media_assets_post_id", "post_id"),
        Index("idx_media_assets_platform_post_id", "platform", "platform_post_id"),
        Index("idx_media_assets_download_status", "download_status"),
    )


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("platform_accounts.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    init_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    init_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    total_posts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_posts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_posts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cursor: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account: Mapped[PlatformAccount] = relationship(back_populates="import_jobs", lazy="raise")

    __table_args__ = (
        CheckConstraint("platform IN ('weibo', 'xueqiu')", name="chk_import_jobs_platform"),
        CheckConstraint("init_mode IN ('none', 'recent', 'all')", name="chk_import_jobs_init_mode"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'paused', 'cancelled')",
            name="chk_import_jobs_status",
        ),
        Index("idx_import_jobs_account_id", "account_id"),
        Index("idx_import_jobs_status", "status"),
        Index("idx_import_jobs_created_at", "created_at"),
    )


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    reference_id: Mapped[str | None] = mapped_column(String(128))
    reference_type: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('new_post', 'edited_post', 'login_expired', 'import_failed', "
            "'media_download_failed', 'worker_error', 'system')",
            name="chk_notification_events_event_type",
        ),
        CheckConstraint(
            "platform IS NULL OR platform IN ('weibo', 'xueqiu')",
            name="chk_notification_events_platform",
        ),
        CheckConstraint("channel IN ('feishu', 'wecom')", name="chk_notification_events_channel"),
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="chk_notification_events_status"),
        Index("idx_notification_events_event_type", "event_type"),
        Index("idx_notification_events_status", "status"),
        Index("idx_notification_events_created_at", "created_at"),
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    value: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(32), nullable=False, default="string")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("value_type IN ('string', 'number', 'bool', 'json')", name="chk_system_settings_value_type"),
    )


class WorkerRunLog(Base):
    __tablename__ = "worker_run_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    worker_name: Mapped[str] = mapped_column(String(128), nullable=False)
    task_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('running', 'success', 'failed')", name="chk_worker_run_logs_status"),
        Index("idx_worker_run_logs_worker_name", "worker_name"),
        Index("idx_worker_run_logs_task_name", "task_name"),
        Index("idx_worker_run_logs_status", "status"),
        Index("idx_worker_run_logs_created_at", "created_at"),
    )
