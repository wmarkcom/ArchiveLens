# Platform Probe

用于最快验证微博、雪球是否能在用户授权登录态下采集目标博主内容。

这个目录是 spike，不连接数据库，不依赖前端 UI。目标是确认：

1. 登录态能否复用。
2. 博主主页能否访问。
3. 是否能提取候选正文、发布时间、原文链接、图片 URL。
4. 是否能从页面网络 JSON 中找到更稳定的数据源。
5. 是否能判断历史分页能力。

## 准备

激活 Conda 环境：

```bash
conda activate archivelens
```

首次使用需要安装 Playwright 浏览器：

```bash
python -m playwright install chromium
```

## 登录并保存 session

账号密码不要写入脚本，也不要发给任何人。脚本会打开浏览器，你手动登录。

微博：

```bash
python spikes/platform_probe/login_weibo.py
```

雪球：

```bash
python spikes/platform_probe/login_xueqiu.py
```

登录完成后，在终端按 Enter。脚本会保存：

```text
auth/weibo.json
auth/xueqiu.json
```

`auth/` 已被 `.gitignore` 忽略。

## 探测博主主页

微博：

```bash
python spikes/platform_probe/probe_weibo.py "https://weibo.com/u/目标ID"
```

雪球：

```bash
python spikes/platform_probe/probe_xueqiu.py "https://xueqiu.com/u/目标ID"
```

输出会保存到：

```text
spikes/platform_probe/output/
```

每次输出包含：

1. 页面标题、最终 URL。
2. 当前视口截图，用于诊断页面是否登录成功。
3. 页面链接、图片 URL。
4. 网络 JSON 响应中的候选数据。
5. 候选正文图片下载结果。

注意：`*.png` 是页面诊断截图，不是正文图片归档。正文候选图片会单独下载到：

```text
spikes/platform_probe/output/{platform}_{timestamp}_media/
```

## 判断标准

验证通过的最低标准：

1. 能用保存的 session 打开目标博主主页。
2. 输出里能看到至少一条候选内容正文。
3. 输出里能找到稳定的内容 ID 或详情链接。
4. 输出里能找到图片 URL 或确认该平台该博主无图片。
5. 可以通过滚动或网络 JSON 判断是否支持历史分页。
