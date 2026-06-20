<template>
  <div class="page-stack">
    <section class="stats-grid">
      <StatCard label="监控博主" :value="String(stats.accounts)" helper="已启用 / 总数" tone="blue" />
      <StatCard label="归档内容" :value="String(stats.posts)" helper="今日新增" tone="green" />
      <StatCard label="媒体文件" :value="stats.media" helper="图片本地保存" tone="purple" />
      <StatCard label="异常任务" :value="String(stats.failed)" helper="登录/下载/采集异常" tone="red" />
    </section>

    <section class="dashboard-grid">
      <PanelCard title="最近归档内容" subtitle="最近采集的内容预览，完整列表在「内容归档」中查看">
        <template #actions>
          <RouterLink class="btn" to="/posts">查看全部</RouterLink>
        </template>
        <div v-if="posts.length === 0 && !loading" class="empty-state">暂无归档内容</div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width:68px">平台</th>
                <th style="width:118px">博主</th>
                <th>内容摘要</th>
                <th style="width:74px">媒体</th>
                <th style="width:92px">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="post in posts" :key="post.id">
                <td><strong>{{ platformName(post.platform) }}</strong></td>
                <td>{{ post.account_name }}</td>
                <td>
                  <div class="post-summary-cell">
                    <img v-if="post.cover_url" class="post-thumb small" :src="post.cover_url" alt="首图缩略图" loading="lazy" />
                    <div class="truncate">{{ post.full_text || '-' }}</div>
                  </div>
                </td>
                <td>{{ post.media_count || 0 }} 资源</td>
                <td><StatusBadge :tone="statusTone(post.status)">{{ statusLabel(post.status) }}</StatusBadge></td>
              </tr>
            </tbody>
          </table>
        </div>
      </PanelCard>

      <div class="side-stack">
        <PanelCard title="系统健康" subtitle="核心服务状态" compact>
          <div class="health-grid">
            <StatusBadge :tone="health.frontend">前端 {{ healthText.frontend }}</StatusBadge>
            <StatusBadge :tone="health.api">后端 API {{ healthText.api }}</StatusBadge>
            <StatusBadge :tone="health.postgres">PostgreSQL {{ healthText.postgres }}</StatusBadge>
            <StatusBadge :tone="health.redis">Redis {{ healthText.redis }}</StatusBadge>
            <StatusBadge :tone="health.worker">Worker {{ healthText.worker }}</StatusBadge>
            <StatusBadge :tone="health.beat">Beat {{ healthText.beat }}</StatusBadge>
            <StatusBadge :tone="health.mediaWorker">Media Worker {{ healthText.mediaWorker }}</StatusBadge>
            <StatusBadge :tone="health.weibo">微博登录 {{ healthText.weibo }}</StatusBadge>
            <StatusBadge :tone="health.xueqiu">雪球登录 {{ healthText.xueqiu }}</StatusBadge>
          </div>
          <p class="helper-note" style="margin-top:20px">Worker、Beat、Media Worker 分别对应检查工人、定时器和图片下载工人。</p>
        </PanelCard>

        <PanelCard title="最近事件" subtitle="关键系统通知" compact>
          <div v-if="notifications.length === 0" class="empty-state" style="min-height:100px">暂无通知</div>
          <div v-else class="timeline">
            <div v-for="evt in notifications" :key="evt.id" class="timeline-item">
              <span class="timeline-dot" :class="`tone-${statusTone(evt.status)}`" />
              <span class="timeline-time" :class="`badge-${statusTone(evt.status)}`">{{ fmtTime(evt.created_at) }}</span>
              <span>{{ evt.title }}</span>
            </div>
          </div>
        </PanelCard>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import PanelCard from '../components/PanelCard.vue'
import StatCard from '../components/StatCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { apiGet } from '../composables/useApi'
import { platformName, statusLabel, statusTone } from '../utils/status'
import type { StatusTone } from '../data/mock'

interface PostItem {
  id: number
  platform: string
  account_name: string
  platform_post_id: string
  original_url: string
  published_at: string | null
  title: string | null
  full_text: string | null
  status: string
  is_edited: boolean
  edit_count: number
  media_count: number
  cover_url: string | null
  last_collected_at: string
}

interface NotifItem {
  id: number
  event_type: string
  platform: string | null
  title: string
  channel: string
  status: string
  created_at: string
}

const loading = ref(true)
const posts = ref<PostItem[]>([])
const notifications = ref<NotifItem[]>([])

const stats = ref({ accounts: 0, posts: 0, media: '0', failed: 0 })
const health = ref<Record<string, StatusTone>>({
  frontend: 'green',
  api: 'green',
  postgres: 'slate',
  redis: 'slate',
  worker: 'slate',
  beat: 'slate',
  mediaWorker: 'slate',
  weibo: 'slate',
  xueqiu: 'slate',
})
const healthText = ref<Record<string, string>>({
  frontend: '正常',
  api: '正常',
  postgres: '检测中',
  redis: '检测中',
  worker: '检测中',
  beat: '检测中',
  mediaWorker: '检测中',
  weibo: '检测中',
  xueqiu: '检测中',
})

async function loadDashboard() {
  try {
    const [summary, conns] = await Promise.all([
      apiGet<any>('/dashboard/summary'),
      apiGet<any>('/connections'),
    ])
    stats.value = {
      accounts: summary?.account_count ?? 0,
      posts: summary?.post_count ?? 0,
      media: formatBytes(summary?.media_total_size ?? 0),
      failed: summary?.failed_task_count ?? 0,
    }
    posts.value = summary?.recent_posts?.slice(0, 4) ?? []
    notifications.value = summary?.recent_events?.slice(0, 5) ?? []
    applyHealth(summary?.health ?? {})

    const connItems = conns?.items ?? []
    for (const c of connItems) {
      if (c.platform === 'weibo') setHealth('weibo', c.status === 'connected' ? 'normal' : 'error')
      if (c.platform === 'xueqiu') setHealth('xueqiu', c.status === 'connected' ? 'normal' : 'warning')
    }
  } catch {
    // dashboard will show empty states on error
  } finally {
    loading.value = false
  }
}

function applyHealth(source: Record<string, string>) {
  setHealth('frontend', source.frontend || 'normal')
  setHealth('api', source.api || 'normal')
  setHealth('postgres', source.postgres)
  setHealth('redis', source.redis)
  setHealth('worker', source.worker)
  setHealth('beat', source.beat)
  setHealth('mediaWorker', source.media_worker)
  setHealth('weibo', source.weibo_login)
  setHealth('xueqiu', source.xueqiu_login)
}

function setHealth(key: string, status?: string) {
  const normalized = status || 'warning'
  health.value[key] = healthTone(normalized)
  healthText.value[key] = healthLabel(normalized)
}

function healthTone(status: string): StatusTone {
  if (['normal', 'connected', 'ok', 'success'].includes(status)) return 'green'
  if (['warning', 'expired', 'pending', 'unknown'].includes(status)) return 'yellow'
  if (['error', 'failed', 'offline'].includes(status)) return 'red'
  return 'slate'
}

function healthLabel(status: string): string {
  if (['normal', 'connected', 'ok', 'success'].includes(status)) return '正常'
  if (status === 'expired') return '过期'
  if (status === 'warning' || status === 'unknown') return '待确认'
  if (status === 'pending') return '等待'
  if (status === 'offline') return '离线'
  if (status === 'error' || status === 'failed') return '异常'
  return '未知'
}

function formatBytes(value: number): string {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function fmtTime(ts: string): string {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

onMounted(loadDashboard)
</script>
