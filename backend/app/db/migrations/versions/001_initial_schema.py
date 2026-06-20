"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # platform_connections
    op.create_table(
        "platform_connections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="disconnected"),
        sa.Column("session_data_encrypted", sa.Text(), nullable=True),
        sa.Column("session_meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform"),
    )
    op.create_index("idx_platform_connections_status", "platform_connections", ["status"])
    op.create_check_constraint(
        "chk_platform_connections_platform", "platform_connections", "platform IN ('weibo', 'xueqiu')"
    )
    op.create_check_constraint(
        "chk_platform_connections_status",
        "platform_connections",
        "status IN ('disconnected', 'pending_login', 'connected', 'expired', 'failed')",
    )

    # platform_login_sessions
    op.create_table(
        "platform_login_sessions",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("login_url", sa.Text(), nullable=True),
        sa.Column("callback_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW() + INTERVAL '15 minutes'"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_platform_login_sessions_platform_status", "platform_login_sessions", ["platform", "status"]
    )
    op.create_index("idx_platform_login_sessions_expires_at", "platform_login_sessions", ["expires_at"])
    op.create_check_constraint(
        "chk_platform_login_sessions_platform",
        "platform_login_sessions",
        "platform IN ('weibo', 'xueqiu')",
    )
    op.create_check_constraint(
        "chk_platform_login_sessions_status",
        "platform_login_sessions",
        "status IN ('pending', 'opened', 'success', 'failed', 'expired')",
    )

    # platform_accounts
    op.create_table(
        "platform_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("profile_url", sa.Text(), nullable=False),
        sa.Column("platform_account_id", sa.String(255), nullable=True),
        sa.Column("check_interval", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("init_mode", sa.String(32), nullable=False, server_default="recent"),
        sa.Column("init_limit", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(32), nullable=False, server_default="normal"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_post_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_platform_accounts_platform_account_id",
        "platform_accounts",
        ["platform", "platform_account_id"],
        unique=True,
        postgresql_where=sa.text("platform_account_id IS NOT NULL"),
    )
    op.create_index("idx_platform_accounts_platform", "platform_accounts", ["platform"])
    op.create_index("idx_platform_accounts_enabled", "platform_accounts", ["is_enabled"])
    op.create_index("idx_platform_accounts_status", "platform_accounts", ["status"])
    op.create_check_constraint(
        "chk_platform_accounts_platform", "platform_accounts", "platform IN ('weibo', 'xueqiu')"
    )
    op.create_check_constraint(
        "chk_platform_accounts_init_mode",
        "platform_accounts",
        "init_mode IN ('none', 'recent', 'all')",
    )
    op.create_check_constraint(
        "chk_platform_accounts_status",
        "platform_accounts",
        "status IN ('normal', 'disabled', 'failed')",
    )
    op.create_check_constraint(
        "chk_platform_accounts_check_interval", "platform_accounts", "check_interval >= 60"
    )
    op.create_check_constraint("chk_platform_accounts_init_limit", "platform_accounts", "init_limit >= 0")

    # posts
    op.create_table(
        "posts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("platform_accounts.id"), nullable=False),
        sa.Column("platform_post_id", sa.String(128), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("repost_text", sa.Text(), nullable=True),
        sa.Column("image_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("video_cover_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_edited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("edit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="normal"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_posts_platform_post_id", "posts", ["platform", "platform_post_id"], unique=True)
    op.create_index("idx_posts_account_id", "posts", ["account_id"])
    op.create_index("idx_posts_platform", "posts", ["platform"])
    op.create_index("idx_posts_status", "posts", ["status"])
    op.create_index("idx_posts_published_at", "posts", ["published_at"])
    op.create_index("idx_posts_last_collected_at", "posts", ["last_collected_at"])
    op.create_check_constraint("chk_posts_platform", "posts", "platform IN ('weibo', 'xueqiu')")
    op.create_check_constraint(
        "chk_posts_status", "posts", "status IN ('normal', 'edited', 'deleted', 'hidden', 'failed')"
    )

    # post_snapshots
    op.create_table(
        "post_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.BigInteger(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("platform_post_id", sa.String(128), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("repost_text", sa.Text(), nullable=True),
        sa.Column("image_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("video_cover_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_post_snapshots_post_version", "post_snapshots", ["post_id", "version"], unique=True)
    op.create_index("idx_post_snapshots_post_id", "post_snapshots", ["post_id"])
    op.create_index("idx_post_snapshots_captured_at", "post_snapshots", ["captured_at"])

    # media_assets
    op.create_table(
        "media_assets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.BigInteger(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_post_id", sa.String(128), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(64), nullable=True),
        sa.Column("download_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_media_assets_post_id", "media_assets", ["post_id"])
    op.create_index("idx_media_assets_platform_post_id", "media_assets", ["platform", "platform_post_id"])
    op.create_index("idx_media_assets_download_status", "media_assets", ["download_status"])
    op.create_check_constraint(
        "chk_media_assets_platform", "media_assets", "platform IN ('weibo', 'xueqiu')"
    )
    op.create_check_constraint(
        "chk_media_assets_asset_type", "media_assets", "asset_type IN ('image', 'video_cover')"
    )
    op.create_check_constraint(
        "chk_media_assets_download_status",
        "media_assets",
        "download_status IN ('pending', 'downloading', 'success', 'failed')",
    )

    # import_jobs
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("platform_accounts.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("init_mode", sa.String(32), nullable=False),
        sa.Column("init_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("total_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_import_jobs_account_id", "import_jobs", ["account_id"])
    op.create_index("idx_import_jobs_status", "import_jobs", ["status"])
    op.create_index("idx_import_jobs_created_at", "import_jobs", ["created_at"])
    op.create_check_constraint(
        "chk_import_jobs_platform", "import_jobs", "platform IN ('weibo', 'xueqiu')"
    )
    op.create_check_constraint(
        "chk_import_jobs_init_mode", "import_jobs", "init_mode IN ('none', 'recent', 'all')"
    )
    op.create_check_constraint(
        "chk_import_jobs_status",
        "import_jobs",
        "status IN ('pending', 'running', 'completed', 'failed', 'paused', 'cancelled')",
    )

    # notification_events
    op.create_table(
        "notification_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.String(128), nullable=True),
        sa.Column("reference_type", sa.String(64), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notification_events_event_type", "notification_events", ["event_type"])
    op.create_index("idx_notification_events_status", "notification_events", ["status"])
    op.create_index("idx_notification_events_created_at", "notification_events", ["created_at"])
    op.create_check_constraint(
        "chk_notification_events_event_type",
        "notification_events",
        "event_type IN ('new_post', 'edited_post', 'login_expired', 'import_failed', "
        "'media_download_failed', 'worker_error', 'system')",
    )
    op.create_check_constraint(
        "chk_notification_events_platform",
        "notification_events",
        "platform IS NULL OR platform IN ('weibo', 'xueqiu')",
    )
    op.create_check_constraint(
        "chk_notification_events_channel", "notification_events", "channel IN ('feishu', 'wecom')"
    )
    op.create_check_constraint(
        "chk_notification_events_status",
        "notification_events",
        "status IN ('pending', 'sent', 'failed')",
    )

    # system_settings
    op.create_table(
        "system_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("value_type", sa.String(32), nullable=False, server_default="string"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_check_constraint(
        "chk_system_settings_value_type",
        "system_settings",
        "value_type IN ('string', 'number', 'bool', 'json')",
    )

    # worker_run_logs
    op.create_table(
        "worker_run_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("worker_name", sa.String(128), nullable=False),
        sa.Column("task_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_worker_run_logs_worker_name", "worker_run_logs", ["worker_name"])
    op.create_index("idx_worker_run_logs_task_name", "worker_run_logs", ["task_name"])
    op.create_index("idx_worker_run_logs_status", "worker_run_logs", ["status"])
    op.create_index("idx_worker_run_logs_created_at", "worker_run_logs", ["created_at"])
    op.create_check_constraint(
        "chk_worker_run_logs_status", "worker_run_logs", "status IN ('running', 'success', 'failed')"
    )

    # Triggers for updated_at
    for table in [
        "platform_connections",
        "platform_accounts",
        "posts",
        "media_assets",
        "import_jobs",
        "notification_events",
        "system_settings",
    ]:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at();
        """)

    # Seed system settings
    op.execute("""
        INSERT INTO system_settings (key, value, value_type, description)
        VALUES
          ('default_check_interval', '300', 'number', '默认检查频率，单位秒'),
          ('default_init_limit', '100', 'number', '默认导入最近 N 条历史内容'),
          ('media_root', '/data/media', 'string', '媒体文件本地保存根目录'),
          ('image_download_enabled', 'true', 'bool', '是否下载图片到本地'),
          ('video_cover_download_enabled', 'true', 'bool', '是否下载视频封面到本地'),
          ('video_file_download_enabled', 'false', 'bool', '是否下载视频本体，第一版默认关闭'),
          ('feishu_webhook', '', 'string', '飞书机器人 Webhook'),
          ('wecom_webhook', '', 'string', '企业微信机器人 Webhook'),
          ('daily_backup_enabled', 'true', 'bool', '是否启用每日数据库备份'),
          ('backup_keep_days', '7', 'number', '备份保留天数'),
          ('backup_time', '03:00', 'string', '每日备份时间')
        ON CONFLICT (key) DO NOTHING;
    """)


def downgrade() -> None:
    for table in [
        "worker_run_logs",
        "system_settings",
        "notification_events",
        "import_jobs",
        "media_assets",
        "post_snapshots",
        "posts",
        "platform_accounts",
        "platform_login_sessions",
        "platform_connections",
    ]:
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS set_updated_at CASCADE")
