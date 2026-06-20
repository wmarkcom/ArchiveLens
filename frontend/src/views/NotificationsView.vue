<template>
  <div class="page-stack">
    <PanelCard compact>
      <div class="filters-card">
        <div class="field">
          <label>事件类型</label>
          <select v-model="filters.event_type" @change="loadNotifications">
            <option value="">全部类型</option>
            <option value="new_post">新内容</option>
            <option value="edited_post">内容编辑</option>
            <option value="login_expired">登录过期</option>
            <option value="import_failed">导入失败</option>
            <option value="media_download_failed">媒体下载失败</option>
            <option value="worker_error">Worker 异常</option>
            <option value="system">系统</option>
          </select>
        </div>
        <div class="field">
          <label>渠道</label>
          <select v-model="filters.channel" @change="loadNotifications">
            <option value="">全部渠道</option>
            <option value="feishu">飞书</option>
            <option value="wecom">企业微信</option>
          </select>
        </div>
        <div class="field">
          <label>状态</label>
          <select v-model="filters.status" @change="loadNotifications">
            <option value="">全部状态</option>
            <option value="pending">等待发送</option>
            <option value="sent">已发送</option>
            <option value="failed">失败</option>
          </select>
        </div>
        <div style="align-self:end">
          <button class="btn primary" @click="loadNotifications">刷新</button>
        </div>
      </div>
    </PanelCard>

    <PanelCard title="通知记录" subtitle="查看新内容、编辑、登录过期和任务异常通知">
      <p v-if="feedback.message" class="inline-feedback" :class="feedback.type">{{ feedback.message }}</p>
      <div v-if="notifications.length === 0 && !loading" class="empty-state">暂无通知记录</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:120px">时间</th>
              <th style="width:100px">事件类型</th>
              <th style="width:80px">平台</th>
              <th>标题</th>
              <th style="width:80px">渠道</th>
              <th style="width:80px">状态</th>
              <th style="width:70px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="evt in notifications" :key="evt.id">
              <td>{{ evt.created_at ? fmtTime(evt.created_at) : '-' }}</td>
              <td><StatusBadge :tone="eventTypeTone(evt.event_type)">{{ eventTypeLabel(evt.event_type) }}</StatusBadge></td>
              <td><strong>{{ platformName(evt.platform || 'system') }}</strong></td>
              <td>{{ evt.title }}</td>
              <td>{{ channelLabel(evt.channel) }}</td>
              <td><StatusBadge :tone="statusTone(evt.status)">{{ statusLabel(evt.status) }}</StatusBadge></td>
              <td>
                <button v-if="evt.status === 'failed'" class="btn text" :disabled="retryingId === evt.id" @click="retryNotification(evt.id)">
                  {{ retryingId === evt.id ? '提交中…' : '重发' }}
                </button>
                <span v-else style="color:#94a3b8;font-size:12px">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </PanelCard>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import PanelCard from '../components/PanelCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { apiGet, apiPost } from '../composables/useApi'
import { getApiErrorMessage } from '../utils/apiError'
import { platformName, statusLabel, statusTone } from '../utils/status'

interface Notification {
  id: number
  event_type: string
  platform: string | null
  title: string
  channel: string
  status: string
  created_at: string
}

const loading = ref(true)
const notifications = ref<Notification[]>([])
const filters = reactive({ event_type: '', channel: '', status: '' })
const retryingId = ref<number | null>(null)
const feedback = reactive<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' })

async function loadNotifications() {
  loading.value = true
  const params: Record<string, any> = { page_size: 50 }
  if (filters.event_type) params.event_type = filters.event_type
  if (filters.channel) params.channel = filters.channel
  if (filters.status) params.status = filters.status
  try {
    const res = await apiGet<any>('/notifications', params)
    notifications.value = res?.items ?? []
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '加载通知记录失败')
  }
  loading.value = false
}

async function retryNotification(id: number) {
  retryingId.value = id
  feedback.message = ''
  try {
    const res = await apiPost<{ message?: string }>(`/notifications/${id}/resend`)
    feedback.type = 'success'
    feedback.message = res.message || '通知已重新排队'
    await loadNotifications()
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '重发通知失败')
  } finally {
    retryingId.value = null
  }
}

function eventTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    new_post: '新内容', edited_post: '编辑', login_expired: '登录过期',
    import_failed: '导入失败', media_download_failed: '下载失败',
    worker_error: 'Worker异常', system: '系统',
  }
  return labels[type] ?? type
}

function eventTypeTone(type: string): "blue" | "yellow" | "red" | "slate" {
  if (type === 'new_post') return 'blue'
  if (type === 'edited_post') return 'yellow'
  if (['login_expired', 'import_failed', 'media_download_failed', 'worker_error'].includes(type)) return 'red'
  return 'slate'
}

function channelLabel(channel: string): string {
  return channel === 'feishu' ? '飞书' : channel === 'wecom' ? '企业微信' : channel
}

function fmtTime(ts: string): string {
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

onMounted(loadNotifications)
</script>
