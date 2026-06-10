# 单用户多平台博主内容监控归档系统开发文档

版本：v1.0  
类型：MVP 开发文档  
对应 Figma 高保真稿：https://www.figma.com/design/0FZXWeY7VkvH8uFEUCeBD2

---

## 1. 项目概述

本项目是一个部署在云服务器上的单用户后台系统，用于监控指定微博、雪球博主的内容更新，并将正文、图片、视频封面、原文链接、编辑历史等信息进行本地归档。

系统面向单个管理员使用，不做用户注册、不做多租户、不做复杂权限系统。管理员通过后台绑定微博 / 雪球账号，系统保存登录 session，后台 Worker 使用该 session 定时监控指定博主内容。

---

## 2. 系统目标

### 2.1 核心目标

1. 支持绑定微博、雪球账号。
2. 保存登录 session，并在过期后提醒重新登录。
3. 支持添加需要监控的博主。
4. 支持初始化导入历史内容。
5. 支持定时监控新内容。
6. 支持识别内容是否发生编辑。
7. 支持完整保存正文、图片、视频封面、原文链接。
8. 支持图片本地下载归档。
9. 支持内容搜索、筛选、查看详情。
10. 支持通知推送新内容、编辑、异常状态。
11. 支持 Docker Compose 云服务器部署。

### 2.2 第一版不做

1. 不做多用户系统。
2. 不做复杂权限管理。
3. 不做移动端 App。
4. 不做视频本体下载。
5. 不做对象存储。
6. 不做大规模爬虫集群。
7. 不做验证码绕过。
8. 不做代理池、Cookie 池、风控规避。
9. 不做 AI 自动分类的复杂功能。

---

## 3. 使用边界与安全原则

本系统只用于用户自己授权登录后的内容归档。

### 3.1 允许实现

1. 用户手动登录平台。
2. 后端加密保存 session。
3. Worker 使用已授权 session 读取用户可访问范围内的内容。
4. 正常频率监控指定博主。
5. 图片、正文、链接本地归档。
6. 登录过期后提醒用户重新登录。

### 3.2 不实现

1. 验证码绕过。
2. 平台风控绕过。
3. Cookie 池共享。
4. 代理池伪装。
5. 高频请求攻击。
6. 未授权内容抓取。

---

## 4. 功能范围

### 4.1 平台连接

支持平台：微博、雪球。

平台连接状态：

| 状态 | 说明 |
|---|---|
| disconnected | 未连接 |
| pending_login | 正在登录 |
| connected | 已连接 |
| expired | 登录过期 |
| failed | 登录失败 |

管理员可以执行：绑定平台、重新登录、解绑平台、查看最近登录时间、查看平台状态。

### 4.2 博主管理

管理员可以添加需要监控的博主。

| 字段 | 说明 |
|---|---|
| platform | 平台，微博 / 雪球 |
| account_name | 博主名称 |
| profile_url | 博主主页链接 |
| platform_account_id | 平台账号 ID |
| check_interval | 检查频率 |
| is_enabled | 是否启用 |
| init_mode | 初始化方式 |
| last_checked_at | 最近检测时间 |

初始化方式：

1. 只从现在开始监控，不导入历史。
2. 导入最近 N 条历史内容，默认 100。
3. 导入全部历史内容。

推荐默认策略：导入最近 100 条建立 baseline，同时启动正常监控，后台低优先级继续补全更早历史。

### 4.3 内容归档

系统需要保存每条内容的最新状态和历史快照。

保存内容包括：平台、博主、平台原始 post_id、发布时间、正文、转发正文、图片列表、视频封面、外链、原文链接、内容 hash、内容状态、采集时间、编辑历史。

| 状态 | 说明 |
|---|---|
| normal | 正常 |
| edited | 内容发生编辑 |
| deleted | 内容已删除 |
| hidden | 内容不可见 |
| failed | 采集失败 |

### 4.4 媒体资源

第一版重点保存图片和视频封面。

图片保存策略：

1. 图片必须本地下载。
2. 保存原始 URL。
3. 保存本地路径。
4. 保存下载状态。
5. 下载失败支持重试。
6. 前端优先展示本地文件。

视频策略：第一版只保存视频链接和视频封面图，视频本体后续版本再做。

| 状态 | 说明 |
|---|---|
| pending | 等待下载 |
| downloading | 下载中 |
| success | 下载成功 |
| failed | 下载失败 |

### 4.5 通知记录

系统需要推送以下事件：新内容归档、内容发生编辑、平台登录过期、导入任务失败、图片下载失败、Worker 异常、系统配置保存成功。

通知渠道：飞书机器人、企业微信机器人。

| 状态 | 说明 |
|---|---|
| pending | 待发送 |
| sent | 已发送 |
| failed | 发送失败 |

发送失败后需要记录错误信息，并支持手动重发。

---

## 5. 页面清单

### 5.1 设计说明画布

这些不是实际网页，不需要开发成路由：

| 编号 | 名称 | 说明 |
|---|---|---|
| 00 | 设计系统 / Design System | 颜色、字体、组件规范 |
| 11 | 交互流程 / User Flow | 页面顺序、使用流程、Worker 流程 |
| 12 | 状态与弹窗 / States & Modals | 弹窗、空状态、加载态、失败态 |

### 5.2 实际后台页面

这些需要开发成真实页面：

| 编号 | 页面 | 路由建议 |
|---|---|---|
| 01 | 总览 Dashboard | `/dashboard` |
| 02 | 平台连接 | `/connections` |
| 03 | 监控博主列表 | `/accounts` |
| 04 | 添加监控博主 | `/accounts/new` |
| 05 | 导入任务 | `/import-jobs` |
| 06 | 内容归档列表 | `/posts` |
| 07 | 内容详情 | `/posts/:id` |
| 08 | 媒体资源 | `/media` |
| 09 | 通知记录 | `/notifications` |
| 10 | 系统设置 | `/settings` |

---

## 6. 交互流程

### 6.1 首次使用流程

```text
系统设置
→ 配置域名、媒体目录、通知渠道
→ 平台连接
→ 绑定微博 / 雪球
→ 添加监控博主
→ 选择初始化方式
→ 创建导入任务
→ 导入历史内容
→ 内容归档
```

### 6.2 日常使用流程

```text
总览
→ 查看最近归档内容
→ 点击查看全部
→ 内容归档列表
→ 内容详情
→ 查看正文、图片、历史版本
```

```text
总览
→ 查看最近事件
→ 点击查看全部
→ 通知记录
→ 处理异常
```

### 6.3 异常处理流程

登录过期：

```text
Worker 检测 session 失效
→ platform_connections.status = expired
→ 生成通知记录
→ 推送重新登录提醒
→ 管理员进入平台连接页
→ 重新登录
→ 更新 session
```

导入失败：

```text
导入任务运行失败
→ import_jobs.status = failed
→ 保存 error_message
→ 通知记录生成失败事件
→ 管理员点击重试
→ 从 cursor 断点继续
```

图片下载失败：

```text
media-worker 下载失败
→ media_assets.download_status = failed
→ 保存 error_message
→ 媒体资源页展示失败状态
→ 管理员手动重试
```

---

## 7. 技术架构

### 7.1 推荐技术栈

后端：

| 技术 | 用途 |
|---|---|
| Python 3.11+ | 后端主语言 |
| FastAPI | API 服务 |
| SQLAlchemy / SQLModel | ORM |
| Alembic | 数据库迁移 |
| PostgreSQL | 主数据库 |
| Redis | 队列 / 缓存 |
| Celery | 异步任务 |
| Celery Beat / APScheduler | 定时调度 |
| Playwright | 登录态检测与页面访问 |
| httpx / aiohttp | HTTP 请求 |
| Docker Compose | 部署编排 |

前端：

| 技术 | 用途 |
|---|---|
| Vue 3 | 前端框架 |
| Vite | 构建工具 |
| TypeScript | 类型约束 |
| Element Plus / Ant Design Vue | 后台 UI 组件 |
| Pinia | 状态管理 |
| Vue Router | 路由管理 |
| Axios | API 请求 |

部署：

| 技术 | 用途 |
|---|---|
| Nginx | 反向代理 |
| Certbot / acme.sh | HTTPS 证书 |
| Docker | 容器化 |
| Docker Compose | 多服务编排 |

---

## 8. 系统服务组成

```text
nginx
  └── 反向代理、HTTPS、静态资源

frontend
  └── Vue 管理后台

backend
  └── FastAPI API 服务

worker
  └── 内容监控、历史导入、状态检测

media-worker
  └── 图片、视频封面下载

beat
  └── 定时调度任务

postgres
  └── 业务数据库

redis
  └── Celery 队列、缓存
```

---

## 9. 数据库设计

### 9.1 platform_connections

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| platform | varchar | 平台：weibo / xueqiu |
| status | varchar | disconnected / connected / expired / failed |
| session_data_encrypted | text | 加密后的 session |
| last_login_at | datetime | 最近登录时间 |
| expired_at | datetime | 过期时间 |
| error_message | text | 错误信息 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 9.2 platform_accounts

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| platform | varchar | 平台 |
| account_name | varchar | 博主名称 |
| profile_url | text | 主页链接 |
| platform_account_id | varchar | 平台账号 ID |
| check_interval | int | 检查频率，单位秒 |
| is_enabled | bool | 是否启用 |
| init_mode | varchar | 初始化方式 |
| init_limit | int | 初始化条数 |
| last_checked_at | datetime | 最近检测时间 |
| status | varchar | normal / disabled / failed |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 9.3 posts

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| platform | varchar | 平台 |
| account_id | bigint | 关联博主 |
| platform_post_id | varchar | 平台原始内容 ID |
| title | varchar | 标题 |
| full_text | text | 正文 |
| repost_text | text | 转发正文 |
| original_url | text | 原文链接 |
| published_at | datetime | 发布时间 |
| content_hash | varchar | 内容 hash |
| status | varchar | normal / edited / deleted / hidden |
| first_collected_at | datetime | 首次采集时间 |
| last_collected_at | datetime | 最近采集时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

唯一索引：

```sql
UNIQUE(platform, platform_post_id)
```

### 9.4 post_snapshots

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| post_id | bigint | 关联 posts |
| content_hash | varchar | 快照 hash |
| title | varchar | 标题 |
| full_text | text | 正文 |
| repost_text | text | 转发正文 |
| raw_data | jsonb | 原始数据 |
| captured_at | datetime | 采集时间 |

### 9.5 media_assets

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| post_id | bigint | 关联内容 |
| media_type | varchar | image / video_cover |
| original_url | text | 原始 URL |
| local_path | text | 本地路径 |
| file_size | bigint | 文件大小 |
| mime_type | varchar | 文件类型 |
| download_status | varchar | pending / success / failed |
| retry_count | int | 重试次数 |
| error_message | text | 错误信息 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 9.6 import_jobs

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| account_id | bigint | 关联博主 |
| platform | varchar | 平台 |
| mode | varchar | recent / all |
| target_count | int | 目标数量 |
| imported_count | int | 已导入数量 |
| cursor | text | 分页 cursor |
| status | varchar | pending / running / completed / failed / paused |
| error_message | text | 错误信息 |
| started_at | datetime | 开始时间 |
| finished_at | datetime | 完成时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 9.7 notification_events

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| event_type | varchar | new_post / edited_post / login_expired / import_failed |
| platform | varchar | 平台 |
| title | varchar | 通知标题 |
| content | text | 通知内容 |
| channel | varchar | feishu / wecom |
| status | varchar | pending / sent / failed |
| error_message | text | 错误信息 |
| sent_at | datetime | 发送时间 |
| created_at | datetime | 创建时间 |

### 9.8 system_settings

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 主键 |
| key | varchar | 配置 key |
| value | text | 配置 value |
| value_type | varchar | string / number / bool / json |
| description | text | 说明 |
| updated_at | datetime | 更新时间 |

---

## 10. 内容变化判断机制

### 10.1 post_id 判断新旧

```text
数据库不存在 platform + platform_post_id
→ 新内容
```

```text
数据库存在 platform + platform_post_id
→ 进入 hash 对比
```

### 10.2 content_hash 判断编辑

参与 hash 的字段：title、full_text、repost_text、images、videos、links。

不参与 hash 的字段：点赞数、评论数、转发数、阅读数、页面展示样式、动态热度数据。

### 10.3 删除 / 隐藏判断

```text
数据库有
平台连续多次检测不到
missing_count >= 3
→ 标记为 deleted 或 hidden
```

不要第一次检测不到就标记删除，避免平台接口临时异常造成误判。

---

## 11. API 接口设计

### 11.1 平台连接

#### GET /api/connections

获取所有平台连接状态。

响应示例：

```json
{
  "items": [
    {
      "platform": "weibo",
      "status": "expired",
      "last_login_at": "2026-06-09 09:12:00"
    },
    {
      "platform": "xueqiu",
      "status": "connected",
      "last_login_at": "2026-06-09 09:12:00"
    }
  ]
}
```

#### POST /api/connections/{platform}/login

创建平台登录流程。

响应示例：

```json
{
  "login_session_id": "abc123",
  "login_url": "https://your-domain.com/login-sessions/weibo/abc123"
}
```

#### POST /api/connections/{platform}/logout

解绑平台并清空 session。

#### GET /api/connections/{platform}/status

获取单个平台状态。

#### POST /api/connections/{platform}/refresh

刷新或重新检测平台状态。

### 11.2 博主管理

#### GET /api/accounts

查询监控博主列表。

查询参数：platform、keyword、status、page、page_size。

#### POST /api/accounts

新增监控博主。

请求示例：

```json
{
  "platform": "weibo",
  "profile_url": "https://weibo.com/u/xxxx",
  "account_name": "产品观察者",
  "check_interval": 300,
  "init_mode": "recent",
  "init_limit": 100
}
```

#### GET /api/accounts/{id}

获取博主详情。

#### PUT /api/accounts/{id}

更新博主配置。

#### DELETE /api/accounts/{id}

删除博主。

#### POST /api/accounts/{id}/enable

启用监控。

#### POST /api/accounts/{id}/disable

停用监控。

#### POST /api/accounts/{id}/check-now

立即检测一次。

#### POST /api/accounts/{id}/reimport

重新导入历史内容。

### 11.3 内容归档

#### GET /api/posts

查询内容列表。

查询参数：platform、account_id、keyword、status、date_start、date_end、page、page_size。

#### GET /api/posts/{id}

获取内容详情。

#### GET /api/posts/{id}/snapshots

获取历史版本。

#### GET /api/posts/search

全文搜索内容。

### 11.4 导入任务

#### GET /api/import-jobs

查询导入任务列表。

#### GET /api/import-jobs/{id}

查看任务详情。

#### POST /api/import-jobs/{id}/pause

暂停任务。

#### POST /api/import-jobs/{id}/resume

继续任务。

#### POST /api/import-jobs/{id}/cancel

取消任务。

#### POST /api/import-jobs/{id}/retry

重试失败任务。

### 11.5 媒体资源

#### GET /api/media

查询媒体资源列表。

#### GET /api/media/{asset_id}

查看媒体资源详情。

#### POST /api/media/{asset_id}/retry

重试下载。

#### GET /api/posts/{id}/media

查看某条内容的媒体资源。

### 11.6 通知记录

#### GET /api/notifications

查询通知记录。

#### POST /api/notifications/{id}/resend

重新发送通知。

### 11.7 系统设置

#### GET /api/settings

获取系统设置。

#### PUT /api/settings

保存系统设置。

请求示例：

```json
{
  "default_check_interval": 300,
  "default_init_limit": 100,
  "media_root": "/data/media",
  "feishu_webhook": "https://open.feishu.cn/xxx",
  "wecom_webhook": "https://qyapi.weixin.qq.com/xxx",
  "daily_backup_enabled": true,
  "backup_keep_days": 7
}
```

---

## 12. Worker 任务设计

### 12.1 定时监控任务

```text
Beat 定时触发
→ 查询 enabled accounts
→ 加载对应 platform session
→ 拉取博主最新内容
→ 判断 post_id 是否存在
→ 判断 content_hash 是否变化
→ 保存 posts
→ 保存 post_snapshots
→ 投递 media-worker 下载图片
→ 创建 notification_event
```

### 12.2 历史导入任务

```text
创建 import_job
→ status = pending
→ Worker 拉取任务
→ status = running
→ 按 cursor 分页拉取历史内容
→ 保存 posts / snapshots
→ 保存 cursor
→ 达到目标数量或无更多内容
→ status = completed
```

失败时：

```text
status = failed
保存 error_message
保留 cursor
允许 retry
```

### 12.3 媒体下载任务

```text
接收 media_asset_id
→ 下载 original_url
→ 保存到 local_path
→ 更新 file_size / mime_type
→ download_status = success
```

失败时：

```text
download_status = failed
retry_count + 1
保存 error_message
允许手动 retry
```

---

## 13. 媒体文件保存方案

保存目录：

```text
/data/media/
├── weibo/
│   └── 2026/
│       └── 06/
│           └── 09/
│               └── post_123456/
│                   ├── image_1.jpg
│                   ├── image_2.jpg
│                   └── cover.jpg
└── xueqiu/
    └── 2026/
        └── 06/
            └── 09/
                └── post_987654/
                    ├── image_1.jpg
                    └── image_2.jpg
```

命名规则：

```text
/data/media/{platform}/{yyyy}/{mm}/{dd}/post_{platform_post_id}/image_{index}.{ext}
```

Docker Compose 挂载：

```yaml
volumes:
  - ./data/media:/data/media
```

---

## 14. 前端开发说明

### 14.1 页面布局

所有实际后台页面使用统一布局：

```text
左侧导航栏：248px
顶部状态栏：76px
主内容区：剩余宽度
页面背景：#F6F8FC
卡片背景：#FFFFFF
边框：#E2E8F0
主色：#2563EB
```

### 14.2 Dashboard 规则

总览页只做预览，不做内部滚动列表。

总览页展示：监控博主数量、归档内容数量、媒体文件占用、异常任务数量、最近归档内容 4 条、系统健康状态、最近事件 3 条。

完整数据进入：内容归档列表、通知记录、媒体资源、导入任务。

### 14.3 列表页规则

列表页统一支持：搜索、筛选、分页、状态标签、单行操作、空状态、加载状态、错误状态。

### 14.4 弹窗规则

需要实现：平台绑定登录弹窗、登录成功弹窗、解绑确认弹窗、删除确认弹窗、导入失败重试弹窗、图片预览弹窗、历史版本对比弹窗。

---

## 15. 后端开发说明

### 15.1 项目结构建议

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── connections.py
│   │   ├── accounts.py
│   │   ├── posts.py
│   │   ├── import_jobs.py
│   │   ├── media.py
│   │   ├── notifications.py
│   │   └── settings.py
│   ├── models/
│   ├── schemas/
│   ├── services/
│   │   ├── platform/
│   │   │   ├── weibo.py
│   │   │   └── xueqiu.py
│   │   ├── monitor.py
│   │   ├── media_downloader.py
│   │   ├── notifier.py
│   │   └── hashing.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   ├── monitor_tasks.py
│   │   ├── import_tasks.py
│   │   └── media_tasks.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── logging.py
│   └── db/
│       ├── session.py
│       └── migrations/
└── requirements.txt
```

---

## 16. Docker Compose 部署方案

服务：

```yaml
services:
  nginx:
    image: nginx:latest

  frontend:
    build: ./frontend

  backend:
    build: ./backend

  worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker -l info

  media-worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker -Q media -l info

  beat:
    build: ./backend
    command: celery -A app.workers.celery_app beat -l info

  postgres:
    image: postgres:16

  redis:
    image: redis:7
```

关键挂载：

```yaml
volumes:
  - ./data/postgres:/var/lib/postgresql/data
  - ./data/media:/data/media
  - ./data/logs:/app/logs
```

---

## 17. 云服务器配置

最低配置：

| 配置 | 说明 |
|---|---|
| CPU | 2 核 |
| 内存 | 4 GB |
| 磁盘 | 80 GB |
| 系统 | Ubuntu 22.04 / 24.04 |

推荐配置：

| 配置 | 说明 |
|---|---|
| CPU | 4 核 |
| 内存 | 8 GB |
| 磁盘 | 200 GB |
| 系统 | Ubuntu 22.04 / 24.04 |

长期保存大量图片：

| 配置 | 说明 |
|---|---|
| 磁盘 | 500 GB+ |
| 备选 | MinIO / OSS / COS / S3 |

---

## 18. 开发里程碑

### 阶段 1：基础框架

1. 初始化 FastAPI 项目。
2. 初始化 Vue 项目。
3. 配置 PostgreSQL。
4. 配置 Redis。
5. 配置 Celery。
6. 完成 Docker Compose 基础部署。

### 阶段 2：平台连接

1. 平台连接页面。
2. 平台登录流程。
3. session 加密保存。
4. 登录状态检测。
5. 登录过期提醒。

### 阶段 3：博主管理

1. 博主列表。
2. 添加博主。
3. 启用 / 停用。
4. 初始化方式选择。
5. 创建导入任务。

### 阶段 4：内容归档

1. 定时监控任务。
2. post_id 去重。
3. content_hash 对比。
4. posts 保存。
5. snapshots 保存。
6. 内容详情页。

### 阶段 5：媒体归档

1. media_assets 表。
2. 图片下载任务。
3. 本地文件保存。
4. 下载失败重试。
5. 媒体资源页面。

### 阶段 6：通知与异常

1. 通知记录。
2. 飞书通知。
3. 企业微信通知。
4. 登录过期通知。
5. 导入失败通知。
6. 图片下载失败通知。

### 阶段 7：部署上线

1. Nginx 配置。
2. HTTPS 配置。
3. Docker Compose 启动。
4. 数据库备份。
5. 日志管理。
6. 系统健康检查。

---

## 19. 验收标准

### 19.1 功能验收

1. 可以绑定微博账号。
2. 可以绑定雪球账号。
3. session 过期后可以提醒重新登录。
4. 可以添加监控博主。
5. 可以选择初始化方式。
6. 可以导入最近 N 条历史内容。
7. 可以保存新内容。
8. 可以识别内容编辑。
9. 可以保存图片到本地。
10. 可以查看内容详情。
11. 可以查看历史版本。
12. 可以查看通知记录。
13. 可以重试失败任务。
14. 可以通过 Docker Compose 部署。

### 19.2 UI 验收

1. 页面和 Figma 01-10 对齐。
2. Dashboard 不做滚动长列表。
3. 内容归档、通知记录、媒体资源使用分页。
4. 状态标签颜色和设计系统一致。
5. 空状态、加载态、失败态完整。
6. 弹窗交互完整。

### 19.3 数据验收

1. posts 不重复。
2. platform + platform_post_id 唯一。
3. 内容编辑后生成 post_snapshots。
4. 图片下载成功后 local_path 可访问。
5. 下载失败有 error_message。
6. 导入失败保留 cursor。
7. 通知失败可重发。

---

## 20. 后续可扩展方向
标签自动提取。
多用户权限。
定时导出备份。

