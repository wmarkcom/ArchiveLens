# ArchiveLens

单用户多平台博主内容监控归档系统，用于通过授权登录态监控微博、雪球博主内容，并归档正文、图片、视频封面、原文链接和编辑历史。

ArchiveLens is a self-hosted content archiving dashboard for monitoring authorized public posts from Weibo and Xueqiu.

## 项目亮点

- 授权登录态采集：复用用户自己的微博 / 雪球登录态，不提供验证码绕过、代理池或 Cookie 共享能力。
- 内容归档闭环：保存正文、图片、视频封面、原文链接、发布时间、编辑状态和历史快照。
- 后台管理 UI：提供平台连接、监控博主、导入任务、内容归档、媒体资源、通知记录、运行日志和系统设置页面。
- 异步任务架构：通过 Celery worker、beat、media-worker 分离监控、导入和媒体下载任务。
- 可部署 MVP：包含 Docker Compose、本地开发环境、生产部署说明和数据库迁移。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| Backend | FastAPI, SQLAlchemy, Alembic, Celery |
| Frontend | Vue 3, Vite, TypeScript, Pinia |
| Storage | PostgreSQL, Redis, local media archive |
| Platform probes | Playwright, HTTP platform adapters |
| Deployment | Docker Compose, NGINX frontend proxy |

## 文档

项目文档已集中放在 `docs/`：

- `docs/database_sql_schema.md`：PostgreSQL 建表脚本说明
- `docs/development_plan.md`：MVP 优先开发计划
- `docs/deployment.md`：Linux 云服务器 / Docker Compose 部署说明
- `docs/weibo_adapter_notes.md`：微博适配器采集说明

## 当前工程状态

当前已具备微博监控归档闭环，并已加入雪球平台适配基础：

- `backend/`：FastAPI、SQLAlchemy、Celery、Alembic
- `backend/app/core/errors.py`：统一错误响应结构
- `backend/app/core/security.py`：单用户 Bearer Token 鉴权依赖
- `frontend/`：Vue 3、Vite、TypeScript 后台管理页
- `docker-compose.yml`：PostgreSQL、Redis、后端、Worker、Beat、前端、NGINX 编排
- `.env.example`：环境变量模板
- `spikes/platform_probe/`：微博 / 雪球采集可行性验证脚本

已实现的核心页面包括总览、平台连接、监控博主、导入任务、内容归档、媒体资源、通知记录、运行日志和系统设置。

## 功能状态

| 功能 | 状态 |
| --- | --- |
| 微博授权登录态检测 | 已实现 |
| 微博最近内容采集与详情补全 | 已实现 |
| 雪球 UID 解析与内容标准化 | 已实现基础能力 |
| 内容去重、快照和编辑检测 | 已实现 |
| 媒体资源入库与下载队列 | 已实现 |
| 后台页面与 API 联调 | 已实现 MVP |
| Docker 本地 / 生产部署 | 已实现 |
| 多用户权限体系 | 暂不在 MVP 范围内 |

## 系统架构

```text
Vue 3 admin UI
  |
  | /api/*
  v
FastAPI backend
  |-- PostgreSQL: accounts, posts, snapshots, media, jobs, logs
  |-- Redis: Celery broker and queues
  |
  | tasks
  v
Celery workers
  |-- monitor worker: scheduled account checks
  |-- import worker: historical imports
  |-- media worker: image and cover archival
  v
Authorized platform sessions
  |-- Weibo adapter
  |-- Xueqiu adapter
```

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

## Roadmap

- 完善雪球完整采集分页和登录态失效处理。
- 增强内容搜索、标签和导出能力。
- 增加媒体下载失败的批量重试与空间占用统计。
- 补充更多 API、worker 和前端交互测试。
- 发布 `v0.1.0` Release，固化首个公开 MVP 版本。

## License

ArchiveLens is released under the MIT License. See `LICENSE` for details.
