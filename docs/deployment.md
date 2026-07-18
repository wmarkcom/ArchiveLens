# ArchiveLens 云服务器部署说明

本文档描述生产部署方案。它与本地开发环境分离：

- 本地开发继续使用当前 `.env`、Vite、uvicorn、Celery 命令。
- 生产部署使用 `.env.prod` 和 `docker-compose.prod.yml`。
- 生产入口为 `http://服务器IP:10000`。
- 不占用 `80 / 443 / 8080`。
- 不启动项目自带的最外层 `nginx`。
- 不启动项目自带的 PostgreSQL / Redis，复用服务器上已有数据库容器。

## 生产服务结构

```text
浏览器
  ↓ http://服务器IP:10000
frontend 容器，宿主机 10000 -> 容器内 80
  ├─ 静态页面
  ├─ /api/* -> backend:8000
  └─ /media-files/* -> backend:8000/media-files/*

backend 容器，不暴露公网端口
worker 容器，执行微博/雪球检查和导入任务
beat 容器，定时投递检查任务
media-worker 容器，下载图片到本地归档目录

PostgreSQL / Redis 使用服务器已有容器，通过 host.docker.internal 访问宿主机端口
```

## 目录约定

```text
ArchiveLens/
├── .env.prod
├── docker-compose.prod.yml
├── data/
│   ├── auth/      # 平台登录态，容器内为 /data/auth
│   ├── media/     # 图片和视频封面归档，容器内为 /data/media
│   └── logs/      # Celery beat schedule 和运行日志
└── ...
```

生产部署不使用本项目的 `data/postgres` 和 `data/redis`，因为数据库/Redis 已由服务器现有容器提供。

生产环境的数据落盘位置要按“宿主机路径”和“容器内路径”区分：

| 用途 | 服务器宿主机路径 | 容器内路径 | 说明 |
| --- | --- | --- | --- |
| 登录态 JSON | `/home/ubuntu/project/ArchiveLens/data/auth` | `/data/auth` | 保存 `weibo.json`、`xueqiu.json` |
| 媒体文件 | `/home/ubuntu/project/ArchiveLens/data/media` | `/data/media` | media-worker 下载的微博/雪球图片、视频封面 |
| 运行日志/beat 状态 | `/home/ubuntu/project/ArchiveLens/data/logs` | `/app/logs` | Celery beat schedule 和运行日志 |

例如云端下载后的图片，在服务器上直接看：

```bash
cd /home/ubuntu/project/ArchiveLens
find data/media -type f | head
du -sh data/media
```

如果进入容器排查，则对应看：

```bash
docker exec -it archivelens-prod-media-worker sh
find /data/media -type f | head
```

注意：`.env.prod` 里的 `MEDIA_ROOT=/data/media`、`AUTH_ROOT=/data/auth` 是容器内路径，不是服务器宿主机路径；宿主机路径由 `docker-compose.prod.yml` 的 volume 映射负责挂载。

## 首次准备

在服务器项目目录执行：

```bash
cp .env.prod.example .env.prod
mkdir -p data/auth data/media data/logs
```

编辑 `.env.prod`：

- `ADMIN_TOKEN`：后台登录 Token，必须换成长随机值。
- `SESSION_SECRET_KEY`：会话密钥，必须换成长随机值。
- `CORS_ORIGINS=http://服务器IP:10000`
- `DATABASE_URL`：填写服务器已有 PostgreSQL 的连接地址。
- `REDIS_URL`：填写服务器已有 Redis 的连接地址。
- `MEDIA_ROOT=/data/media`
- `AUTH_ROOT=/data/auth`
- `WEIBO_DETAIL_FALLBACK_LIMIT=3`：每轮最多补全文的微博条数；生产环境不要设太大。
- `WEIBO_DETAIL_TIMEOUT_MS=10000`：微博详情页补全文单页超时，避免 Playwright 长时间卡住。
- `WEIBO_LIST_TIMEOUT_MS=30000`：微博轻量列表接口总超时；列表采集不会启动 Chromium。
- `MONITOR_CHECK_SOFT_TIME_LIMIT=180`：单个博主检查任务软超时秒数。
- `MONITOR_CHECK_TIME_LIMIT=240`：单个博主检查任务硬超时秒数。
- `MONITOR_QUEUE_WARNING_THRESHOLD=100`、`MONITOR_QUEUE_CRITICAL_THRESHOLD=500`：检查队列告警阈值。
- `MEDIA_QUEUE_WARNING_THRESHOLD=500`、`MEDIA_QUEUE_CRITICAL_THRESHOLD=2000`：媒体队列告警阈值。

如果 PostgreSQL / Redis 容器已把端口发布到宿主机，推荐在容器内通过 `host.docker.internal` 访问：

```env
DATABASE_URL=postgresql+psycopg://用户:密码@host.docker.internal:5434/archivelens
REDIS_URL=redis://:密码@host.docker.internal:6380/0
```

`docker-compose.prod.yml` 已包含：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

因此 Linux Docker 容器可以访问宿主机发布端口。

## 登录态迁移

把本地生成好的登录态上传到服务器：

```bash
scp auth/weibo.json user@server:/path/to/ArchiveLens/data/auth/weibo.json
scp auth/xueqiu.json user@server:/path/to/ArchiveLens/data/auth/xueqiu.json
```

部署后打开 `http://服务器IP:10000`，进入“平台连接”，点击“重新检测”，确认微博和雪球都显示已登录。

## 启动生产服务

启动前可先做配置解析校验，不会启动容器：

```bash
ARCHIVELENS_ENV_FILE=.env.prod docker compose -f docker-compose.prod.yml --env-file .env.prod config
```

```bash
sudo docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

如果这次部署包含 Dockerfile、依赖、前端构建或 compose 配置变更，建议强制重新构建：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod build --no-cache backend worker media-worker beat frontend
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build --force-recreate
```

访问：

```text
http://服务器IP:10000
```

生产 compose 只暴露一个宿主机端口：

```text
10000 -> frontend:80
```

`backend` 只在 Docker 网络内被 frontend 和 workers 访问，不暴露公网。

## 部署前同步清单

如果是在本地改完代码后手动上传到服务器，至少确认这些文件已同步到服务器项目目录：

```text
docker-compose.prod.yml
.env.prod
backend/Dockerfile
frontend/Dockerfile
frontend/nginx.conf
backend/
frontend/
docs/
```

尤其要确认服务器上的后端 Dockerfile 第一行：

```bash
cd /home/ubuntu/project/ArchiveLens
sed -n '1,3p' backend/Dockerfile
```

必须是：

```dockerfile
FROM python:3.12-slim-bookworm
```

不要使用：

```dockerfile
FROM python:3.12-slim
FROM python:3.12-bookworm-slim
```

原因：

- `python:3.12-slim` 当前可能对应 Debian trixie，Playwright 安装依赖时容易出现字体包不存在。
- `python:3.12-bookworm-slim` 不是 Docker 官方 Python 镜像标签，会报 `not found`。
- `python:3.12-slim-bookworm` 是这套部署当前使用的稳定标签。

## 查看状态

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f worker
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f media-worker
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f beat
```

也可以在后台页面查看：

```text
/dashboard
/worker-logs
```

## 更新部署

拉取或上传新代码后：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

`backend` 启动时会自动执行：

```bash
alembic upgrade head
```

因此后续数据库迁移会随后端启动自动应用。

## 常见问题

### 打开页面后提示填写后台访问 Token

这是正常的。浏览器本地保存的旧 Token 和云端 `.env.prod` 不一致时，前端会要求重新填写。

在服务器查看：

```bash
cd /home/ubuntu/project/ArchiveLens
grep '^ADMIN_TOKEN=' .env.prod
```

复制等号后面的值填入弹窗。不要使用本地开发 `.env` 的 Token。

### 页面打不开

确认服务器防火墙和云厂商安全组开放 `10000`：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

### 页面打开但接口失败

前端容器内部会代理：

- `/api/*` -> `backend:8000`
- `/media-files/*` -> `backend:8000/media-files/*`

检查 backend：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend
```

### 数据库或 Redis 连不上

在服务器宿主机先确认已有容器端口能访问：

```bash
nc -vz 127.0.0.1 5434
nc -vz 127.0.0.1 6380
```

如果宿主机端口不是 `5434 / 6380`，同步修改 `.env.prod` 里的 `DATABASE_URL` / `REDIS_URL`。

### 构建卡在 apt-get 或 Playwright

如果日志卡在类似：

```text
RUN apt-get update
RUN python -m playwright install --with-deps chromium
```

先不要急着中断。国内服务器拉 Debian / Python / npm 依赖可能较慢，本项目 Dockerfile 已配置清华源和 npm 镜像源：

- `backend/Dockerfile`：Debian 清华源，pip 清华源。
- `frontend/Dockerfile`：Alpine 清华源，npm 使用 npmmirror。

如果最终失败，再按下面错误类型处理。

### Playwright 报 ttf-unifont 或 ttf-ubuntu-font-family 不存在

典型错误：

```text
E: Package 'ttf-unifont' has no installation candidate
E: Package 'ttf-ubuntu-font-family' has no installation candidate
```

这通常说明服务器还在用旧的 `backend/Dockerfile`，镜像仍是：

```dockerfile
FROM python:3.12-slim
```

检查服务器文件：

```bash
cd /home/ubuntu/project/ArchiveLens
sed -n '1,3p' backend/Dockerfile
```

如果不是 `python:3.12-slim-bookworm`，重新上传本地的 `backend/Dockerfile` 后清缓存构建：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod build --no-cache backend worker media-worker beat
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build --force-recreate
```

### python:3.12-bookworm-slim not found

典型错误：

```text
python:3.12-bookworm-slim: not found
```

这是镜像标签写反了。正确值是：

```dockerfile
FROM python:3.12-slim-bookworm
```

修改后重新上传 `backend/Dockerfile` 并执行：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod build --no-cache backend worker media-worker beat
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build --force-recreate
```

### 登录态失效

重新在本机生成：

```bash
python spikes/platform_probe/login_weibo.py
python spikes/platform_probe/login_xueqiu.py
```

然后到后台“平台连接”上传新的 JSON，或覆盖服务器文件：

```bash
scp auth/weibo.json user@server:/path/to/ArchiveLens/data/auth/weibo.json
scp auth/xueqiu.json user@server:/path/to/ArchiveLens/data/auth/xueqiu.json
```

### 图片不显示

确认 `data/media` 已挂载，且 media worker 正常：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f media-worker
```

### 微博长正文没有采全

微博列表接口 `/ajax/statuses/mymblog` 有时只返回摘要文本，长微博需要打开详情页再补全文。

当前生产策略是：使用轻量 HTTP 客户端直接请求列表接口，自动采集最新内容，列表阶段不启动 Chromium；详情页只对“新微博”或“疑似截断微博”做限量补全文，并且详情页有短超时兜底。

确认 `.env.prod` 配置：

```bash
cd /home/ubuntu/project/ArchiveLens
grep -E '^(WEIBO_|MONITOR_|MEDIA_QUEUE_)' .env.prod
```

推荐值：

```env
WEIBO_DETAIL_FALLBACK_LIMIT=3
WEIBO_DETAIL_TIMEOUT_MS=10000
WEIBO_LIST_TIMEOUT_MS=30000
MONITOR_CHECK_SOFT_TIME_LIMIT=180
MONITOR_CHECK_TIME_LIMIT=240
MONITOR_QUEUE_WARNING_THRESHOLD=100
MONITOR_QUEUE_CRITICAL_THRESHOLD=500
MEDIA_QUEUE_WARNING_THRESHOLD=500
MEDIA_QUEUE_CRITICAL_THRESHOLD=2000
```

不要把 `WEIBO_DETAIL_FALLBACK_LIMIT` 长期设为 `20` 这类较大值，否则微博详情页/Chromium 可能拖慢 worker，造成 Redis 队列积压。生产 Worker 使用 `prefork` 单并发和 `max-tasks-per-child`，Celery 超时可以真正终止卡死任务；相关容器启用了 `init: true`，负责回收 Chromium 孤儿进程。修改后需要强制重建相关容器，让 `.env.prod` 和 compose 配置重新加载：

```bash
sudo docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build --force-recreate backend worker beat
```

如果已经出现 Worker 长时间不消费、任务大量积压，先停 Beat 和 Worker，只清理默认检查队列及监控锁，不要清理 `media` 队列：

```bash
sudo docker compose -f docker-compose.prod.yml --env-file .env.prod stop beat worker
sudo docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend python - <<'PY'
from redis import Redis
from app.core.config import settings

r = Redis.from_url(settings.redis_url, decode_responses=True)
print("queued monitor tasks:", r.llen("celery"))
r.delete("celery")
keys = list(r.scan_iter("archivelens:monitor:account:*:scheduled"))
if keys:
    r.delete(*keys)
print("deleted locks:", len(keys))
PY
sudo docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build --force-recreate backend worker media-worker beat
ps -eo stat= | awk '$1 ~ /^Z/ {n++} END {print "zombie processes:", n+0}'
```

微博登录失效时，系统会把微博连接标记为 `expired`，停止继续调度微博账号；重新扫码登录或上传并检测新的 `weibo.json` 后，系统会恢复连接并立即触发一次扫描。

## 备份建议

至少定期备份：

- `data/auth`
- `data/media`
- 服务器已有 PostgreSQL 数据库
- 服务器已有 Redis 数据

`.env.prod` 包含密钥，不要提交 Git。
