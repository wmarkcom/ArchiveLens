# ArchiveLens

单用户多平台博主内容监控归档系统，用于通过授权登录态监控微博、雪球博主内容，并归档正文、图片、视频封面、原文链接和编辑历史。

## 文档

项目文档已集中放在 `docs/`：

- `docs/database_sql_schema.md`：PostgreSQL 建表脚本说明
- `docs/development_plan.md`：MVP 优先开发计划
- `docs/deployment.md`：Linux 云服务器 / Docker Compose 部署说明
- `docs/weibo_adapter_notes.md`：微博适配器采集说明

## 当前工程状态

当前已具备微博单平台闭环：

- `backend/`：FastAPI、SQLAlchemy、Celery、Alembic
- `backend/app/core/errors.py`：统一错误响应结构
- `backend/app/core/security.py`：单用户 Bearer Token 鉴权依赖
- `frontend/`：Vue 3、Vite、TypeScript 后台管理页
- `docker-compose.yml`：PostgreSQL、Redis、后端、Worker、Beat、前端、NGINX 编排
- `.env.example`：环境变量模板
- `spikes/platform_probe/`：微博 / 雪球采集可行性验证脚本

已实现的核心页面包括总览、平台连接、监控博主、导入任务、内容归档、媒体资源、通知记录、运行日志和系统设置。

## 最快验证采集可行性

优先使用 `spikes/platform_probe/`，先验证平台授权 session 是否能采集目标博主数据，再继续完整 UI 和数据库开发。

```bash
conda activate archivelens
python -m playwright install chromium
python spikes/platform_probe/login_weibo.py
python spikes/platform_probe/probe_weibo.py "https://weibo.com/u/目标ID"
```

雪球：

```bash
python spikes/platform_probe/login_xueqiu.py
python spikes/platform_probe/probe_xueqiu.py "https://xueqiu.com/u/目标ID"
```

采集输出保存在 `spikes/platform_probe/output/`，登录态保存在 `auth/`。这两个目录都不会提交到 Git。

## 本地启动

### Conda 开发环境

本项目推荐使用独立 Conda 环境开发，避免污染 `base`：

```bash
conda env create -f environment.yml
conda activate archivelens
```

如果后续修改了 Python 依赖：

```bash
conda env update -f environment.yml --prune
```

### 环境变量

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 在 `.env` 中填写 PostgreSQL、Redis 和后台密钥。真实 `.env` 已被 `.gitignore` 忽略，不要提交。

本地已有外部数据库服务时，按实际地址填写：

```text
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
REDIS_HOST=localhost
REDIS_PORT=6380
DATABASE_URL=postgresql+psycopg://<postgres_user>:<postgres_password>@localhost:5434/<database_name>
REDIS_URL=redis://:<redis_password>@localhost:6380/0
```

### 本地进程启动

后端：

```bash
uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

Celery worker：

```bash
PYTHONPATH=backend celery -A app.workers.celery_app worker -l info --pool=solo --concurrency=1
```

Celery beat：

```bash
PYTHONPATH=backend celery -A app.workers.celery_app beat -l info --pidfile=
```

媒体下载 worker：

```bash
PYTHONPATH=backend celery -A app.workers.celery_app worker -Q media -l info --pool=solo --concurrency=1
```

### Docker 启动

服务器或本机安装 Docker 后，可以使用 Compose 启动：

```bash
cp .env.example .env
mkdir -p data/auth data/media data/postgres data/redis data/logs
docker compose up --build
```

访问：

- 后台入口：http://localhost:8080
- 前端容器直连：http://localhost:5173
- 后端健康检查：http://localhost:8000/health

微博登录态在 Docker 中挂载到 `data/auth/weibo.json`。无桌面 Linux 服务器可以运行采集和定时监控，但首次登录建议先在本机生成 `auth/weibo.json`，再到后台 `平台连接` 页面上传替换；也可以手动复制到服务器 `data/auth/weibo.json`。

更多细节见 `docs/deployment.md`。

## 密钥管理

不要把真实 `.env`、Redis 密码、PostgreSQL 密码、平台 session、webhook URL 提交到 Git。
