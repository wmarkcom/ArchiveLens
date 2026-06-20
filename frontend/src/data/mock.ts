export type Platform = 'weibo' | 'xueqiu'
export type StatusTone = 'blue' | 'green' | 'yellow' | 'red' | 'slate' | 'purple' | 'cyan'

export interface StatCardData {
  label: string
  value: string
  helper: string
  tone: StatusTone
}

export interface ArchivePost {
  id: number
  platform: Platform
  author: string
  summary: string
  media: string
  status: 'normal' | 'edited' | 'deleted' | 'hidden' | 'failed'
  publishedAt: string
  collectedAt: string
  url: string
  fullText: string
  images: string[]
}

export interface Account {
  id: number
  platform: Platform
  name: string
  profileUrl: string
  accountId: string
  interval: string
  initMode: string
  lastChecked: string
  status: 'normal' | 'disabled' | 'failed'
}

export interface ImportJob {
  id: number
  account: string
  platform: Platform
  mode: string
  progress: number
  imported: number
  total: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused'
  updatedAt: string
}

export interface MediaAsset {
  id: number
  postId: number
  platform: Platform
  type: 'image' | 'video_cover'
  originalUrl: string
  localPath: string
  size: string
  status: 'pending' | 'downloading' | 'success' | 'failed'
  error?: string
}

export interface NotificationEvent {
  id: number
  time: string
  eventType: string
  platform: Platform | 'system'
  title: string
  channel: string
  status: 'pending' | 'sent' | 'failed'
}

export const dashboardStats: StatCardData[] = [
  { label: '监控博主', value: '18', helper: '微博 10 / 雪球 8', tone: 'blue' },
  { label: '归档内容', value: '12,486', helper: '今日新增 24', tone: 'green' },
  { label: '媒体文件', value: '38.2GB', helper: '图片本地保存', tone: 'purple' },
  { label: '异常任务', value: '2', helper: '登录/下载异常', tone: 'red' },
]

export const posts: ArchivePost[] = [
  {
    id: 1,
    platform: 'weibo',
    author: '产品观察者',
    summary: '讨论 AI 产品工作流，含 4 张截图',
    media: '4 图',
    status: 'normal',
    publishedAt: '2026-06-10 10:21',
    collectedAt: '2026-06-10 10:31',
    url: 'https://weibo.com/u/1642512402',
    fullText:
      '今天继续梳理 AI 产品工作流。真正影响体验的不是单点能力，而是从输入、检索、生成、审校到归档的整条链路能否被稳定复用。',
    images: ['image_01.jpg', 'image_02.jpg', 'image_03.jpg', 'image_04.jpg'],
  },
  {
    id: 2,
    platform: 'xueqiu',
    author: '市场随笔',
    summary: '长文后续发生编辑，已保存两个版本',
    media: '2 图',
    status: 'edited',
    publishedAt: '2026-06-10 09:48',
    collectedAt: '2026-06-10 10:20',
    url: 'https://xueqiu.com/u/123456',
    fullText:
      '盘中记录：市场情绪比早盘更分化，原文在 10:16 补充了风险提示，目前系统已保留编辑前后的两个快照。',
    images: ['snapshot_a.jpg', 'snapshot_b.jpg'],
  },
  {
    id: 3,
    platform: 'weibo',
    author: '科技博主A',
    summary: '转发并评论行业新闻，视频封面已归档',
    media: '1 封面',
    status: 'normal',
    publishedAt: '2026-06-10 09:31',
    collectedAt: '2026-06-10 09:58',
    url: 'https://weibo.com/u/778899',
    fullText: '这个发布节奏很有意思，短视频封面和正文信息都已经被归档，后续可以对编辑历史做进一步比对。',
    images: ['cover_01.jpg'],
  },
  {
    id: 4,
    platform: 'xueqiu',
    author: '生活记录',
    summary: '图片动态，全部图片本地保存',
    media: '9 图',
    status: 'normal',
    publishedAt: '2026-06-10 08:42',
    collectedAt: '2026-06-10 09:12',
    url: 'https://xueqiu.com/u/998877',
    fullText: '日常图片动态，九张图已下载到本地媒体目录，前端优先展示本地归档路径。',
    images: ['life_01.jpg', 'life_02.jpg', 'life_03.jpg'],
  },
]

export const accounts: Account[] = [
  {
    id: 1,
    platform: 'weibo',
    name: '产品观察者',
    profileUrl: 'https://weibo.com/u/1642512402',
    accountId: '1642512402',
    interval: '300 秒',
    initMode: '最近 100 条',
    lastChecked: '10:31',
    status: 'normal',
  },
  {
    id: 2,
    platform: 'xueqiu',
    name: '市场随笔',
    profileUrl: 'https://xueqiu.com/u/123456',
    accountId: '123456',
    interval: '600 秒',
    initMode: '最近 100 条',
    lastChecked: '10:20',
    status: 'normal',
  },
  {
    id: 3,
    platform: 'weibo',
    name: '科技博主A',
    profileUrl: 'https://weibo.com/u/778899',
    accountId: '778899',
    interval: '300 秒',
    initMode: '全部历史',
    lastChecked: '09:58',
    status: 'failed',
  },
]

export const importJobs: ImportJob[] = [
  { id: 901, account: '科技博主A', platform: 'weibo', mode: '全部历史', progress: 100, imported: 864, total: 864, status: 'completed', updatedAt: '09:58' },
  { id: 902, account: '市场随笔', platform: 'xueqiu', mode: '最近 100 条', progress: 72, imported: 72, total: 100, status: 'running', updatedAt: '10:20' },
  { id: 903, account: '生活记录', platform: 'xueqiu', mode: '最近 100 条', progress: 18, imported: 18, total: 100, status: 'failed', updatedAt: '09:12' },
]

export const mediaAssets: MediaAsset[] = [
  { id: 501, postId: 1, platform: 'weibo', type: 'image', originalUrl: 'https://wx1.sinaimg.cn/mw2000/a.jpg', localPath: '/data/media/weibo/2026/06/10/image_01.jpg', size: '1.2 MB', status: 'success' },
  { id: 502, postId: 1, platform: 'weibo', type: 'image', originalUrl: 'https://wx1.sinaimg.cn/mw2000/b.jpg', localPath: '/data/media/weibo/2026/06/10/image_02.jpg', size: '960 KB', status: 'success' },
  { id: 503, postId: 3, platform: 'weibo', type: 'video_cover', originalUrl: 'https://wx3.sinaimg.cn/mw2000/c.jpg', localPath: '/data/media/weibo/2026/06/10/cover_01.jpg', size: '482 KB', status: 'success' },
  { id: 504, postId: 4, platform: 'xueqiu', type: 'image', originalUrl: 'https://image.xueqiu.com/d.jpg', localPath: '', size: '-', status: 'failed', error: 'HTTP 403' },
]

export const notifications: NotificationEvent[] = [
  { id: 701, time: '10:31', eventType: '新内容', platform: 'weibo', title: '新内容已归档：产品观察者', channel: '飞书', status: 'sent' },
  { id: 702, time: '10:20', eventType: '登录过期', platform: 'weibo', title: '微博登录态过期，已提醒', channel: '飞书', status: 'sent' },
  { id: 703, time: '09:58', eventType: '导入完成', platform: 'weibo', title: '全量导入完成：科技博主A', channel: '企业微信', status: 'sent' },
  { id: 704, time: '09:12', eventType: '下载失败', platform: 'xueqiu', title: '图片下载失败，已进入重试队列', channel: '飞书', status: 'failed' },
]
