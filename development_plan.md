# 单用户多平台博主内容监控归档系统开发计划

版本：v1.0  
策略：MVP 优先  
依据文档：`devdoc.md`、`database_sql_schema.md`、`openapi_interface_doc.md`、Figma 原型 UI

---

## 1. 开发原则

1. 先验证最不确定的链路：平台授权 session、内容获取、分页、图片下载。
2. 后端接口以 `openapi_interface_doc.md` 为前后端联调契约。
3. 数据库以 `database_sql_schema.md` 为准，主文档中的简化字段不作为最终建表依据。
4. 前端 UI 按 Figma 01-10 页面实现，但早期允许使用 mock 数据。
5. 不实现验证码绕过、代理池、Cookie 池共享、风控规避和视频本体下载。
6. 所有 Worker 任务必须具备幂等、失败记录和可重试能力。
7. Redis、PostgreSQL、webhook、平台 session 等敏感信息只通过 `.env` 或部署平台密钥注入，不写入仓库文档和源码。

---

## 2. 已知环境配置

以下信息用于开发和部署配置。密码不应提交到 Git。

| 服务 | 实例名称 | 版本 | 端口 | 配置建议 |
|---|---|---:|---:|---|
| Redis | ArchiveLens-redis | 8.6.3 | 6380 | 使用 `REDIS_URL` 注入连接串 |
| PostgreSQL | ArchiveLens-postgresql | 18.4 | 5434 | 使用 `DATABASE_URL` 注入连接串 |

建议环境变量：

```text
DATABASE_URL=postgresql+psycopg://<postgres_user>:<postgres_password>@<postgres_host>:5434/<database_name>
REDIS_URL=redis://:<redis_password>@<redis_host>:6380/0
ADMIN_TOKEN=<admin_token>
SESSION_SECRET_KEY=<session_secret_key>
MEDIA_ROOT=/data/media
```

---

## 3. 阶段 0：平台采集可行性验证

目标：在正式铺开后台开发前，确认微博和雪球真实采集链路可行。

交付物：

1. 微博采集 spike：
   - 使用用户授权登录态访问目标博主主页或可用接口。
   - 获取最近内容列表。
   - 获取正文、发布时间、原文链接、图片 URL。
   - 验证历史分页能力。
2. 雪球采集 spike：
   - 使用用户授权登录态访问目标博主主页或可用接口。
   - 获取最近内容列表。
   - 获取正文、发布时间、原文链接、图片 URL。
   - 验证历史分页能力。
3. 输出采集结论：
   - 可稳定获取的字段。
   - 不稳定字段。
   - 推荐请求频率。
   - session 失效表现。
   - 是否支持最近 N 条导入。

验收标准：

1. 微博和雪球至少各能获取一个目标博主的最近内容。
2. 能得到用于去重的 `platform_post_id`。
3. 能构造内容详情原文链接。
4. 能提取图片原始 URL 或可下载 URL。
5. 明确平台不可用或不稳定时的降级方案。

---

## 4. 阶段 1：基础工程骨架

目标：完成可运行的前后端与基础服务环境。

后端交付物：

1. 初始化 FastAPI 项目结构。
2. 配置 SQLAlchemy / SQLModel。
3. 配置 Alembic 迁移。
4. 配置 PostgreSQL 连接。
5. 配置 Redis。
6. 配置 Celery worker、media-worker、beat。
7. 实现统一配置、日志、错误响应结构。
8. 实现简单单用户后台鉴权。

前端交付物：

1. 初始化 Vue 3 + Vite + TypeScript。
2. 配置 Vue Router。
3. 配置 Pinia。
4. 配置 Axios API client。
5. 建立后台统一布局：侧边栏、顶部栏、主内容区。
6. 建立基础状态组件：加载、错误、空状态、分页、状态标签。

部署交付物：

1. `docker-compose.yml`
2. backend Dockerfile
3. frontend Dockerfile
4. Nginx 基础反向代理配置
5. `.env.example`

验收标准：

1. `docker compose up` 可以启动 backend、frontend、postgres、redis。
2. 后端健康检查接口可访问。
3. 前端可打开后台布局。
4. Celery worker 可以启动并执行测试任务。

---

## 5. 阶段 2：数据模型与后端核心 API

目标：按 OpenAPI 和数据库文档跑通核心 CRUD 与任务投递。

数据库交付物：

1. 创建核心表：
   - `platform_connections`
   - `platform_login_sessions`
   - `platform_accounts`
   - `posts`
   - `post_snapshots`
   - `media_assets`
   - `import_jobs`
   - `notification_events`
   - `system_settings`
   - `worker_run_logs`
2. 创建必要索引、唯一约束、CHECK 约束和更新时间触发器。
3. 写入初始系统配置。

API 交付物：

1. Dashboard：
   - `GET /api/dashboard/summary`
2. Connections：
   - `GET /api/connections`
   - `GET /api/connections/{platform}/status`
   - `POST /api/connections/{platform}/login`
   - `POST /api/connections/{platform}/logout`
   - `POST /api/connections/{platform}/refresh`
3. Accounts：
   - `GET /api/accounts`
   - `POST /api/accounts`
   - `GET /api/accounts/{accountId}`
   - `PUT /api/accounts/{accountId}`
   - `DELETE /api/accounts/{accountId}`
   - enable、disable、check-now、reimport
4. Posts、Import Jobs、Media、Notifications、Settings 按 OpenAPI 文档实现。
5. 所有列表接口支持分页。
6. 所有错误响应使用统一格式。

验收标准：

1. OpenAPI 中的 MVP 接口均返回正确结构。
2. 数据库唯一约束能阻止重复内容。
3. API 参数校验、错误码、分页结构一致。
4. 后端测试可覆盖核心 CRUD。

---

## 6. 阶段 3：前端后台 UI 与 Mock 联调

目标：按 Figma 完成真实页面结构，并通过 mock 或后端假数据联调。

页面交付物：

1. `/dashboard` 总览
2. `/connections` 平台连接
3. `/accounts` 监控博主列表
4. `/accounts/new` 添加监控博主
5. `/import-jobs` 导入任务
6. `/posts` 内容归档列表
7. `/posts/:id` 内容详情
8. `/media` 媒体资源
9. `/notifications` 通知记录
10. `/settings` 系统设置

交互交付物：

1. 平台绑定登录弹窗。
2. 登录成功弹窗。
3. 解绑确认弹窗。
4. 删除确认弹窗。
5. 导入失败重试弹窗。
6. 图片预览弹窗。
7. 历史版本对比弹窗。
8. 列表搜索、筛选、分页。
9. 加载态、空状态、错误态。

验收标准：

1. 页面布局与 Figma 01-10 对齐。
2. Dashboard 只展示摘要和预览，不做内部长滚动。
3. 内容归档、通知记录、媒体资源使用分页。
4. 状态标签颜色和设计系统一致。
5. 前端可通过 mock 数据完整走通主要操作流程。

---

## 7. 阶段 4：真实平台 Adapter 与归档主链路

目标：把 mock 采集替换为真实微博 / 雪球 Adapter，跑通核心归档闭环。

后端交付物：

1. 定义统一 Platform Adapter 接口：
   - 登录状态检测
   - 获取账号信息
   - 获取最近内容
   - 分页获取历史内容
   - 标准化平台原始数据
2. 实现 Weibo Adapter。
3. 实现 Xueqiu Adapter。
4. 实现内容标准化模型。
5. 实现 `content_hash` 计算。
6. 实现新内容入库。
7. 实现编辑检测和 `post_snapshots` 写入。
8. 实现 `missing_count >= 3` 后标记 deleted / hidden。
9. 实现 `check-now` 立即检测。
10. 实现最近 N 条历史导入。

Worker 交付物：

1. 定时监控任务。
2. 历史导入任务。
3. 任务幂等控制。
4. 失败记录和 retry。
5. Worker 运行日志。

验收标准：

1. 添加博主后可以导入最近 N 条内容。
2. 定时任务可以发现新内容。
3. 同一平台内容不会重复入库。
4. 内容变化后生成新快照。
5. 登录过期会更新连接状态并产生通知事件。
6. 导入失败保留 cursor，可继续 retry。

---

## 8. 阶段 5：媒体归档、通知与异常处理

目标：补齐图片本地归档、通知推送和异常闭环。

媒体交付物：

1. 图片下载任务。
2. 视频封面下载任务。
3. 本地路径规则：
   - `/data/media/{platform}/{yyyy}/{mm}/{dd}/post_{platform_post_id}/image_{index}.{ext}`
4. 下载状态更新：
   - `pending`
   - `downloading`
   - `success`
   - `failed`
5. 下载失败重试。
6. 前端优先展示本地文件。

通知交付物：

1. 飞书机器人通知。
2. 企业微信机器人通知。
3. 通知事件创建：
   - 新内容
   - 内容编辑
   - 登录过期
   - 导入失败
   - 图片下载失败
   - Worker 异常
4. 通知失败记录 error_message。
5. 通知手动重发。

验收标准：

1. 图片下载成功后 `local_path` 可访问。
2. 图片下载失败有错误信息，可手动重试。
3. 新内容和编辑事件可以生成通知记录。
4. 通知失败后可以手动重发。
5. 媒体资源页可以筛选失败资源。

---

## 9. 阶段 6：部署、备份与上线验收

目标：完成云服务器部署能力和上线前验收。

部署交付物：

1. 生产 Docker Compose 配置。
2. Nginx HTTPS 配置。
3. 媒体目录挂载。
4. 数据库目录挂载。
5. 日志目录挂载。
6. 健康检查。
7. 数据库备份脚本。
8. 备份保留策略。
9. 上线部署说明。

验收标准：

1. Ubuntu 22.04 / 24.04 服务器可部署。
2. HTTPS 可访问后台。
3. 重启服务后数据不丢失。
4. 媒体文件持久化。
5. 数据库备份可生成并清理过期备份。
6. Worker、media-worker、beat 均可自动恢复。

---

## 10. 测试策略

后端测试：

1. 数据模型约束测试。
2. API 参数校验测试。
3. CRUD 接口测试。
4. `content_hash` 稳定性测试。
5. 新内容、编辑内容、重复内容入库测试。
6. 导入任务 retry 测试。
7. 媒体下载失败重试测试。
8. 通知发送失败重试测试。

前端测试：

1. 主要页面渲染测试。
2. 列表筛选和分页测试。
3. 表单校验测试。
4. 弹窗交互测试。
5. API 错误态展示测试。

集成测试：

1. 添加博主 -> 创建导入任务 -> 入库 posts -> 生成 snapshots。
2. 定时检测 -> 发现新内容 -> 下载图片 -> 生成通知。
3. 登录过期 -> 更新连接状态 -> 生成通知。
4. 导入失败 -> 保留 cursor -> retry 成功。
5. 通知失败 -> 手动重发成功。

---

## 11. 风险与默认决策

1. 最大风险是微博 / 雪球采集稳定性，因此阶段 0 必须先做。
2. `导入全部历史内容` 第一版保留后端能力，但前端默认优先使用最近 N 条。
3. 中文搜索第一版使用 PostgreSQL `pg_trgm`，后续数据量变大再考虑搜索引擎。
4. 视频本体下载第一版不做，只保存视频链接和视频封面。
5. 单用户后台第一版使用简单 Bearer Token，后续再扩展完整登录系统。
6. webhook、session 等敏感配置必须加密或通过环境变量管理。
7. 所有 Worker 任务必须以数据库状态为准，不依赖内存状态判断进度。

---

## 12. MVP 验收清单

功能验收：

1. 可以绑定微博账号。
2. 可以绑定雪球账号。
3. session 过期后可以提醒重新登录。
4. 可以添加监控博主。
5. 可以选择最近 N 条初始化导入。
6. 可以保存新内容。
7. 可以识别内容编辑。
8. 可以保存图片到本地。
9. 可以查看内容列表和详情。
10. 可以查看历史版本。
11. 可以查看媒体资源。
12. 可以查看通知记录。
13. 可以重试失败任务。
14. 可以通过 Docker Compose 部署。

数据验收：

1. `posts` 不重复。
2. `platform + platform_post_id` 唯一。
3. 内容编辑后生成 `post_snapshots`。
4. 图片下载成功后 `local_path` 可访问。
5. 下载失败有 `error_message`。
6. 导入失败保留 `cursor`。
7. 通知失败可重发。

UI 验收：

1. 页面和 Figma 01-10 对齐。
2. Dashboard 不做滚动长列表。
3. 列表页支持搜索、筛选、分页。
4. 状态标签颜色统一。
5. 空状态、加载态、失败态完整。
6. 核心弹窗交互完整。
