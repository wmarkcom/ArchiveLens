import type { StatusTone } from '../data/mock'

export function platformName(platform: string): string {
  if (platform === 'weibo') return '微博'
  if (platform === 'xueqiu') return '雪球'
  return '系统'
}

export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    normal: '正常',
    edited: '已编辑',
    deleted: '已删除',
    hidden: '不可见',
    failed: '失败',
    disabled: '已停用',
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    paused: '已暂停',
    downloading: '下载中',
    success: '成功',
    sent: '已发送',
    connected: '已登录',
    expired: '已过期',
    disconnected: '未连接',
  }
  return labels[status] ?? status
}

export function statusTone(status: string): StatusTone {
  if (['normal', 'success', 'sent', 'connected', 'completed'].includes(status)) return 'green'
  if (['edited', 'pending', 'running', 'paused', 'downloading'].includes(status)) return 'yellow'
  if (['failed', 'expired', 'deleted'].includes(status)) return 'red'
  if (['weibo'].includes(status)) return 'blue'
  if (['xueqiu'].includes(status)) return 'cyan'
  return 'slate'
}
