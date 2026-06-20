# 微博采集 Adapter 验证与设计记录

版本：v0.1  
日期：2026-06-10  
状态：微博采集主链路已通过 spike 验证，并已沉淀为后端 `WeiboAdapter`

---

## 1. 结论

微博采集不建议使用纯 DOM。

当前更稳的正式方案是：

```text
collect_weibo_posts(options)
-> 使用用户授权登录态创建浏览器上下文
-> 调微博前端 JSON 接口获取列表
-> 解析结构化字段
-> 对截断正文打开详情页补全
-> 提取图片 URL
-> 后续写入 posts / post_snapshots / media_assets
```

已验证：

1. 保存的 Playwright session 可以复用。
2. 微博列表接口可以返回目标博主内容。
3. 列表接口能拿到 `id`、`mid`、发布时间、正文片段、图片 ID。
4. 列表页正文可能截断，详情页可补全。
5. 图片下载可行，但需要携带 `Referer` 和 `User-Agent`。
6. 头像、会员图标、页面装饰图需要过滤。

---

## 2. 相关代码位置

正式后端 Adapter：

```text
backend/app/services/platform/weibo.py
backend/app/services/platform/base.py
backend/app/services/platform/registry.py
```

核心采集函数：

```python
collect_weibo_posts(options: WeiboCollectOptions) -> PageResult
```

`WeiboAdapter.fetch_history_page()` 只是薄封装，内部调用 `collect_weibo_posts()`。后续 API、Worker、导入任务、测试脚本都应复用这个函数，避免同一条采集链路散落在多个入口里。

采集可行性 spike：

```text
spikes/platform_probe/
```

解析测试样例：

```text
backend/tests/test_weibo_parser.py
```

登录态保存位置：

```text
auth/weibo.json
```

`auth/` 已加入 `.gitignore`，不能提交。

---

## 3. 为什么不是纯 DOM

微博前端页面存在这些问题：

1. 列表页使用懒加载和虚拟滚动。
2. 直接整页截图会出现大量空白和错位。
3. 页面 DOM 会混入头像、会员图标、视频封面、装饰图。
4. 列表页正文常见截断，文本中会出现：

```text
...展开
```

5. DOM class 名称和页面结构容易随微博前端改版变化。

相比之下，微博前端 JSON 接口返回结构化字段，更适合作为主链路。

---

## 4. 当前主链路接口

列表接口：

```text
GET https://weibo.com/ajax/statuses/mymblog?uid={uid}&page={page}&feature=0
```

示例：

```text
https://weibo.com/ajax/statuses/mymblog?uid=1642512402&page=1&feature=0
```

详情页：

```text
https://weibo.com/{uid}/{bid}
```

示例：

```text
https://weibo.com/1642512402/R3t77kc9F
```

登录检测接口：

```text
GET https://weibo.com/ajax/feed/allGroups
```

登录检测还会先检查 `auth/weibo.json` 中是否存在微博 `SUB` cookie。

---

## 5. 字段映射

微博列表接口字段到系统标准字段的当前映射：

| 微博字段 | 系统字段 | 说明 |
|---|---|---|
| `mid` / `id` | `platform_post_id` | 优先使用 `mid` |
| `created_at` | `published_at` | 使用 `email.utils.parsedate_to_datetime` 解析 |
| `text_raw` / `text` | `full_text` | 先清理 HTML，再判断是否需要详情页补全 |
| `mblogid` / `bid` / `mid` / `id` | `original_url` | 拼成 `https://weibo.com/{uid}/{bid}` |
| `pics` / `pic_ids` | `image_urls` | 统一转成可下载图片 URL |
| `page_info.media_info` | `video_cover_urls` | 用于视频封面 |
| `source` | `source` | 微博来源，如“微博网页版” |
| `edit_count` / 文本中的“已编辑” | `is_edited` | 粗略标记编辑状态 |
| 原始 item | `raw_data` | 保存原始 JSON |

标准输出模型：

```python
NormalizedPost(
    platform="weibo",
    platform_post_id="5308269014813287",
    original_url="https://weibo.com/1642512402/R3t77kc9F",
    published_at=datetime(...),
    full_text="...",
    image_urls=[...],
    video_cover_urls=[...],
    source="微博网页版",
    is_edited=True,
    raw_data={...},
)
```

采集函数输入：

```python
WeiboCollectOptions(
    storage_state_path=Path("auth/weibo.json"),
    uid="1642512402",
    page_no=1,
    limit=20,
    headless=True,
    detail_fallback_limit=5,
)
```

采集函数输出：

```python
PageResult(
    items=[NormalizedPost(...), ...],
    next_cursor="2",
)
```

---

## 6. 正文补全策略

列表接口返回的 `text_raw` 可能是截断内容。

判断截断的规则：

1. `text` 中包含：

```html
<span class="expand">展开</span>
```

2. `text` 中包含：

```text
...展开
```

3. `text_raw` 以微博省略标记结尾。

如果判断为截断：

```text
打开 https://weibo.com/{uid}/{bid}
-> 等待页面加载
-> 点击“展开”
-> 从详情页 DOM 中选择最长 article 文本
-> 清理 HTML 和多余空白
```

这个 DOM 只作为详情页补全，不作为列表主采集方式。

---

## 7. 图片处理策略

微博图片 URL 常见形式：

```text
https://wx1.sinaimg.cn/orj360/{pic_id}.jpg
https://wx1.sinaimg.cn/orj480/{pic_id}.jpg
https://wx1.sinaimg.cn/mw2000/{pic_id}.jpg
```

当前策略：

1. 优先使用 `pics[].large.url`。
2. 如果只有 `pic_ids`，拼接：

```text
https://wx1.sinaimg.cn/mw2000/{pic_id}.jpg
```

3. 将展示缩略图路径：

```text
/orj360/
/orj480/
```

正规化为：

```text
/mw2000/
```

4. 过滤头像、会员图标、页面装饰图：

```text
tvax*.sinaimg.cn
tva*.sinaimg.cn
h5.sinaimg.cn/upload
vvip_2.png
```

5. 下载图片时必须携带：

```text
Referer: https://weibo.com/u/{uid}
User-Agent: 浏览器 UA
```

不带这些头时，微博图片容易返回 `HTTP 403`。

---

## 8. 已验证结果

测试目标：

```text
https://weibo.com/u/1642512402
```

测试时间：

```text
2026-06-10
```

spike 输出示例：

```text
spikes/platform_probe/output/weibo_20260610_152828.json
spikes/platform_probe/output/weibo_20260610_152828_media/
```

验证结果：

```text
detail_links: 5
post_details: 5
downloaded_images: 9
图片下载成功: 9/9
```

正式 Adapter 烟测结果：

```text
login: True
items: 2
next: 2
```

示例内容：

```text
platform_post_id: 5308269014813287
full_text length: 993
image_urls: 2
original_url: https://weibo.com/1642512402/R3t77kc9F
```

这说明：

1. 登录态检测可用。
2. 列表接口可用。
3. 下一页 cursor 可推进。
4. 详情页补全文本可用。
5. 图片 URL 提取可用。

---

## 9. 当前限制

1. 微博接口不是正式开放 API，仍可能变化。
2. 详情页 DOM 补全文本是兜底方案，后续仍需寻找更直接的详情 JSON 接口。
3. 图片下载已验证 URL 可提取，但正式落库前还需要媒体下载任务统一处理。
4. `is_edited` 当前只是粗略判断，正式编辑检测仍应依赖 `content_hash`。
5. 当前 Adapter 尚未接数据库、Celery、导入任务和通知系统。

---

## 10. 下一步工程化落地

建议下一步做：

1. 建立数据库模型和 Alembic 迁移。
2. 实现 `posts`、`post_snapshots`、`media_assets` 写入服务。
3. 实现 `content_hash`：

```text
title + full_text + repost_text + image_urls + video_cover_urls + links
```

4. 接入 `WeiboAdapter.fetch_recent_posts()` 到 `check-now`。
5. 新内容写入 `posts` 和首个 `post_snapshots`。
6. 内容变化时更新 `posts` 并新增 `post_snapshots`。
7. 图片 URL 写入 `media_assets`，由 media-worker 下载。
8. 登录过期时更新 `platform_connections.status = expired` 并生成通知事件。

---

## 11. 实现原则

正式微博采集应遵循：

1. 主链路使用 JSON 接口，不依赖列表页 DOM。
2. DOM 只用于详情页补全文本或异常兜底。
3. 所有请求使用用户授权 session。
4. 不做验证码绕过。
5. 不做代理池、Cookie 池、风控规避。
6. 请求频率保守，优先稳定。
7. 所有采集失败都记录错误，不静默吞掉。
