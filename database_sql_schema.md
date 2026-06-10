# 数据库 SQL 建表脚本

项目：单用户多平台博主内容监控归档系统  
数据库：PostgreSQL 16+  
版本：v1.0

---

## 1. 设计说明

本 SQL 适用于 MVP 第一版，核心目标是支持：

1. 平台登录 session 保存。
2. 微博 / 雪球博主管理。
3. 内容归档。
4. 内容历史快照。
5. 图片 / 视频封面本地归档。
6. 历史导入任务。
7. 通知记录。
8. 系统配置。
9. Worker 运行日志。

状态字段暂时使用 `varchar + CHECK`，便于后续迁移和扩展。  
如果后期状态稳定，也可以改成 PostgreSQL ENUM。

---

## 2. 初始化扩展

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

说明：

| 扩展 | 用途 |
|---|---|
| pgcrypto | 生成 UUID、加密辅助 |
| pg_trgm | 后续支持正文模糊搜索 |

---

## 3. 更新时间触发器

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## 4. 平台连接表：platform_connections

```sql
CREATE TABLE IF NOT EXISTS platform_connections (
  id BIGSERIAL PRIMARY KEY,

  platform VARCHAR(32) NOT NULL UNIQUE,
  status VARCHAR(32) NOT NULL DEFAULT 'disconnected',

  session_data_encrypted TEXT,
  session_meta JSONB NOT NULL DEFAULT '{}'::jsonb,

  last_login_at TIMESTAMPTZ,
  expired_at TIMESTAMPTZ,

  error_message TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_platform_connections_platform
    CHECK (platform IN ('weibo', 'xueqiu')),

  CONSTRAINT chk_platform_connections_status
    CHECK (status IN ('disconnected', 'pending_login', 'connected', 'expired', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_platform_connections_status
  ON platform_connections(status);

CREATE TRIGGER trg_platform_connections_updated_at
BEFORE UPDATE ON platform_connections
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

---

## 5. 平台登录会话表：platform_login_sessions

用于记录一次登录流程，例如点击“绑定微博”后生成的临时登录 session。

```sql
CREATE TABLE IF NOT EXISTS platform_login_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  platform VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',

  login_url TEXT,
  callback_payload JSONB NOT NULL DEFAULT '{}'::jsonb,

  error_message TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '15 minutes'),

  CONSTRAINT chk_platform_login_sessions_platform
    CHECK (platform IN ('weibo', 'xueqiu')),

  CONSTRAINT chk_platform_login_sessions_status
    CHECK (status IN ('pending', 'opened', 'success', 'failed', 'expired'))
);

CREATE INDEX IF NOT EXISTS idx_platform_login_sessions_platform_status
  ON platform_login_sessions(platform, status);

CREATE INDEX IF NOT EXISTS idx_platform_login_sessions_expires_at
  ON platform_login_sessions(expires_at);
```

---

## 6. 监控博主表：platform_accounts

```sql
CREATE TABLE IF NOT EXISTS platform_accounts (
  id BIGSERIAL PRIMARY KEY,

  platform VARCHAR(32) NOT NULL,
  account_name VARCHAR(255) NOT NULL,
  profile_url TEXT NOT NULL,
  platform_account_id VARCHAR(255),

  check_interval INTEGER NOT NULL DEFAULT 300,
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,

  init_mode VARCHAR(32) NOT NULL DEFAULT 'recent',
  init_limit INTEGER NOT NULL DEFAULT 100,

  status VARCHAR(32) NOT NULL DEFAULT 'normal',

  last_checked_at TIMESTAMPTZ,
  last_post_published_at TIMESTAMPTZ,

  error_message TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_platform_accounts_platform
    CHECK (platform IN ('weibo', 'xueqiu')),

  CONSTRAINT chk_platform_accounts_init_mode
    CHECK (init_mode IN ('none', 'recent', 'all')),

  CONSTRAINT chk_platform_accounts_status
    CHECK (status IN ('normal', 'disabled', 'failed')),

  CONSTRAINT chk_platform_accounts_check_interval
    CHECK (check_interval >= 60),

  CONSTRAINT chk_platform_accounts_init_limit
    CHECK (init_limit >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_accounts_platform_account_id
  ON platform_accounts(platform, platform_account_id)
  WHERE platform_account_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_platform_accounts_platform
  ON platform_accounts(platform);

CREATE INDEX IF NOT EXISTS idx_platform_accounts_enabled
  ON platform_accounts(is_enabled);

CREATE INDEX IF NOT EXISTS idx_platform_accounts_status
  ON platform_accounts(status);

CREATE TRIGGER trg_platform_accounts_updated_at
BEFORE UPDATE ON platform_accounts
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

---

## 7. 内容主表：posts

保存每条内容的最新版本。

```sql
CREATE TABLE IF NOT EXISTS posts (
  id BIGSERIAL PRIMARY KEY,

  platform VARCHAR(32) NOT NULL,
  account_id BIGINT NOT NULL REFERENCES platform_accounts(id) ON DELETE CASCADE,

  platform_post_id VARCHAR(255) NOT NULL,

  title VARCHAR(500),
  full_text TEXT,
  repost_text TEXT,

  original_url TEXT,
  raw_url TEXT,

  published_at TIMESTAMPTZ,
  first_collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  content_hash VARCHAR(128) NOT NULL,

  status VARCHAR(32) NOT NULL DEFAULT 'normal',
  missing_count INTEGER NOT NULL DEFAULT 0,

  raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_posts_platform
    CHECK (platform IN ('weibo', 'xueqiu')),

  CONSTRAINT chk_posts_status
    CHECK (status IN ('normal', 'edited', 'deleted', 'hidden', 'failed')),

  CONSTRAINT chk_posts_missing_count
    CHECK (missing_count >= 0),

  CONSTRAINT uq_posts_platform_post_id
    UNIQUE(platform, platform_post_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_account_id
  ON posts(account_id);

CREATE INDEX IF NOT EXISTS idx_posts_platform
  ON posts(platform);

CREATE INDEX IF NOT EXISTS idx_posts_status
  ON posts(status);

CREATE INDEX IF NOT EXISTS idx_posts_published_at
  ON posts(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_posts_last_collected_at
  ON posts(last_collected_at DESC);

CREATE INDEX IF NOT EXISTS idx_posts_full_text_trgm
  ON posts USING GIN (full_text gin_trgm_ops);

CREATE TRIGGER trg_posts_updated_at
BEFORE UPDATE ON posts
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

---

## 8. 内容快照表：post_snapshots

每次首次采集或内容变化时写入一条快照。

```sql
CREATE TABLE IF NOT EXISTS post_snapshots (
  id BIGSERIAL PRIMARY KEY,

  post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,

  content_hash VARCHAR(128) NOT NULL,

  title VARCHAR(500),
  full_text TEXT,
  repost_text TEXT,

  raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,

  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_post_snapshots_post_id
  ON post_snapshots(post_id);

CREATE INDEX IF NOT EXISTS idx_post_snapshots_captured_at
  ON post_snapshots(captured_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_post_snapshots_post_hash
  ON post_snapshots(post_id, content_hash);
```

---

## 9. 媒体资源表：media_assets

保存图片、视频封面等本地归档记录。

```sql
CREATE TABLE IF NOT EXISTS media_assets (
  id BIGSERIAL PRIMARY KEY,

  post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,

  media_type VARCHAR(32) NOT NULL,

  original_url TEXT NOT NULL,
  local_path TEXT,

  file_name VARCHAR(255),
  file_size BIGINT,
  mime_type VARCHAR(128),

  width INTEGER,
  height INTEGER,

  download_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  retry_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_media_assets_media_type
    CHECK (media_type IN ('image', 'video_cover')),

  CONSTRAINT chk_media_assets_download_status
    CHECK (download_status IN ('pending', 'downloading', 'success', 'failed')),

  CONSTRAINT chk_media_assets_retry_count
    CHECK (retry_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_media_assets_post_id
  ON media_assets(post_id);

CREATE INDEX IF NOT EXISTS idx_media_assets_download_status
  ON media_assets(download_status);

CREATE INDEX IF NOT EXISTS idx_media_assets_media_type
  ON media_assets(media_type);

CREATE UNIQUE INDEX IF NOT EXISTS uq_media_assets_post_original_url
  ON media_assets(post_id, original_url);

CREATE TRIGGER trg_media_assets_updated_at
BEFORE UPDATE ON media_assets
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

---

## 10. 历史导入任务表：import_jobs

```sql
CREATE TABLE IF NOT EXISTS import_jobs (
  id BIGSERIAL PRIMARY KEY,

  account_id BIGINT NOT NULL REFERENCES platform_accounts(id) ON DELETE CASCADE,
  platform VARCHAR(32) NOT NULL,

  mode VARCHAR(32) NOT NULL,
  target_count INTEGER,
  imported_count INTEGER NOT NULL DEFAULT 0,

  cursor TEXT,

  status VARCHAR(32) NOT NULL DEFAULT 'pending',

  error_message TEXT,

  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_import_jobs_platform
    CHECK (platform IN ('weibo', 'xueqiu')),

  CONSTRAINT chk_import_jobs_mode
    CHECK (mode IN ('recent', 'all')),

  CONSTRAINT chk_import_jobs_status
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'paused', 'cancelled')),

  CONSTRAINT chk_import_jobs_imported_count
    CHECK (imported_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_import_jobs_account_id
  ON import_jobs(account_id);

CREATE INDEX IF NOT EXISTS idx_import_jobs_status
  ON import_jobs(status);

CREATE INDEX IF NOT EXISTS idx_import_jobs_created_at
  ON import_jobs(created_at DESC);

CREATE TRIGGER trg_import_jobs_updated_at
BEFORE UPDATE ON import_jobs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

---

## 11. 通知事件表：notification_events

```sql
CREATE TABLE IF NOT EXISTS notification_events (
  id BIGSERIAL PRIMARY KEY,

  event_type VARCHAR(64) NOT NULL,
  platform VARCHAR(32),

  related_post_id BIGINT REFERENCES posts(id) ON DELETE SET NULL,
  related_account_id BIGINT REFERENCES platform_accounts(id) ON DELETE SET NULL,
  related_import_job_id BIGINT REFERENCES import_jobs(id) ON DELETE SET NULL,
  related_media_asset_id BIGINT REFERENCES media_assets(id) ON DELETE SET NULL,

  title VARCHAR(500) NOT NULL,
  content TEXT,

  channel VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',

  error_message TEXT,
  sent_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_notification_events_event_type
    CHECK (event_type IN (
      'new_post',
      'edited_post',
      'login_expired',
      'import_failed',
      'media_download_failed',
      'worker_error',
      'system'
    )),

  CONSTRAINT chk_notification_events_platform
    CHECK (platform IS NULL OR platform IN ('weibo', 'xueqiu')),

  CONSTRAINT chk_notification_events_channel
    CHECK (channel IN ('feishu', 'wecom')),

  CONSTRAINT chk_notification_events_status
    CHECK (status IN ('pending', 'sent', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_notification_events_event_type
  ON notification_events(event_type);

CREATE INDEX IF NOT EXISTS idx_notification_events_status
  ON notification_events(status);

CREATE INDEX IF NOT EXISTS idx_notification_events_created_at
  ON notification_events(created_at DESC);

CREATE TRIGGER trg_notification_events_updated_at
BEFORE UPDATE ON notification_events
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

---

## 12. 系统设置表：system_settings

```sql
CREATE TABLE IF NOT EXISTS system_settings (
  id BIGSERIAL PRIMARY KEY,

  key VARCHAR(128) NOT NULL UNIQUE,
  value TEXT,
  value_type VARCHAR(32) NOT NULL DEFAULT 'string',
  description TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_system_settings_value_type
    CHECK (value_type IN ('string', 'number', 'bool', 'json'))
);

CREATE TRIGGER trg_system_settings_updated_at
BEFORE UPDATE ON system_settings
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

---

## 13. Worker 运行日志表：worker_run_logs

```sql
CREATE TABLE IF NOT EXISTS worker_run_logs (
  id BIGSERIAL PRIMARY KEY,

  worker_name VARCHAR(128) NOT NULL,
  task_name VARCHAR(128) NOT NULL,

  status VARCHAR(32) NOT NULL,

  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,

  duration_ms INTEGER,

  error_message TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_worker_run_logs_status
    CHECK (status IN ('running', 'success', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_worker_run_logs_worker_name
  ON worker_run_logs(worker_name);

CREATE INDEX IF NOT EXISTS idx_worker_run_logs_task_name
  ON worker_run_logs(task_name);

CREATE INDEX IF NOT EXISTS idx_worker_run_logs_status
  ON worker_run_logs(status);

CREATE INDEX IF NOT EXISTS idx_worker_run_logs_created_at
  ON worker_run_logs(created_at DESC);
```

---

## 14. 初始系统配置

```sql
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
```

---

## 15. 推荐查询示例

### 15.1 查询启用中的监控博主

```sql
SELECT *
FROM platform_accounts
WHERE is_enabled = TRUE
  AND status = 'normal'
ORDER BY last_checked_at NULLS FIRST;
```

### 15.2 查询最近归档内容

```sql
SELECT
  p.id,
  p.platform,
  a.account_name,
  p.full_text,
  p.status,
  p.published_at,
  p.last_collected_at
FROM posts p
JOIN platform_accounts a ON a.id = p.account_id
ORDER BY p.last_collected_at DESC
LIMIT 20;
```

### 15.3 查询下载失败媒体

```sql
SELECT *
FROM media_assets
WHERE download_status = 'failed'
ORDER BY updated_at DESC;
```

### 15.4 查询通知失败记录

```sql
SELECT *
FROM notification_events
WHERE status = 'failed'
ORDER BY created_at DESC;
```

---

## 16. 表关系说明

```text
platform_connections
  └── 保存平台级登录 session

platform_accounts
  └── 一个监控博主

posts
  └── 一个博主下的内容最新版本

post_snapshots
  └── 一条内容的历史版本

media_assets
  └── 一条内容的图片 / 视频封面

import_jobs
  └── 某个博主的历史导入任务

notification_events
  └── 新内容、编辑、登录过期、失败等通知事件

system_settings
  └── 系统配置

worker_run_logs
  └── Worker 执行记录
```
