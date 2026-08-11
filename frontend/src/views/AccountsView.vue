<template>
  <div class="page-stack">
    <PanelCard compact>
      <div class="filters-card">
        <div class="field">
          <label>平台</label>
          <select v-model="filters.platform" @change="loadAccounts">
            <option value="">全部平台</option>
            <option value="weibo">微博</option>
            <option value="xueqiu">雪球</option>
          </select>
        </div>
        <div class="field">
          <label>状态</label>
          <select v-model="filters.status" @change="loadAccounts">
            <option value="">全部状态</option>
            <option value="normal">正常</option>
            <option value="failed">失败</option>
            <option value="disabled">停用</option>
          </select>
        </div>
        <div class="field" style="grid-column:span 2">
          <label>关键词</label>
          <input v-model="filters.keyword" placeholder="搜索博主名称 / 平台 ID" @keyup.enter="loadAccounts" />
        </div>
        <RouterLink class="btn primary" to="/accounts/new">添加博主</RouterLink>
      </div>
    </PanelCard>

    <PanelCard title="监控博主列表" subtitle="添加后可选择最近 N 条初始化导入，并由 Worker 定时检测">
      <p v-if="feedback.message" class="inline-feedback" :class="feedback.type">{{ feedback.message }}</p>
      <div v-if="accounts.length === 0 && !loading" class="empty-state">暂无监控博主，点击「添加博主」开始</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:86px">平台</th>
              <th>博主</th>
              <th>平台 ID</th>
              <th>检查频率</th>
              <th>通知推送</th>
              <th>初始化</th>
              <th>最近检测</th>
              <th>下次检测</th>
              <th>状态</th>
              <th style="width:230px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="acc in accounts" :key="acc.id">
              <td><strong>{{ platformName(acc.platform) }}</strong></td>
              <td>
                <strong>{{ acc.account_name }}</strong>
                <div class="truncate" style="font-size:12px">{{ acc.profile_url }}</div>
              </td>
              <td>{{ acc.platform_account_id || '-' }}</td>
              <td>{{ acc.check_interval }}s</td>
              <td><StatusBadge :tone="acc.notification_enabled ? 'green' : 'slate'">{{ acc.notification_enabled ? '已开启' : '未开启' }}</StatusBadge></td>
              <td>{{ initModeLabel(acc.init_mode) }}</td>
              <td>{{ acc.last_checked_at ? fmtTime(acc.last_checked_at) : '从未' }}</td>
              <td>{{ nextCheckLabel(acc) }}</td>
              <td>
                <StatusBadge :tone="statusTone(acc.status)">{{ statusLabel(acc.status) }}</StatusBadge>
                <div v-if="acc.error_message" class="truncate" style="max-width:180px;margin-top:6px;font-size:12px;color:#dc2626" :title="acc.error_message">
                  {{ acc.error_message }}
                </div>
              </td>
              <td>
                <div class="row-actions">
                  <RouterLink class="btn text" :to="`/accounts/${acc.id}/edit`">编辑</RouterLink>
                  <button class="btn text" :disabled="busyAction(acc.id, 'check')" @click="checkNow(acc.id)">
                    {{ busyAction(acc.id, 'check') ? '提交中…' : '立即检查' }}
                  </button>
                  <button class="btn text" :disabled="busyAction(acc.id, 'reimport')" @click="reimportAccount(acc.id)">
                    {{ busyAction(acc.id, 'reimport') ? '提交中…' : '重新导入' }}
                  </button>
                  <button class="btn text" :disabled="busyAction(acc.id, 'toggle')" @click="toggleAccount(acc)">
                    {{ busyAction(acc.id, 'toggle') ? '处理中…' : (acc.is_enabled ? '停用' : '启用') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="pagination.total > pagination.page_size" style="display:flex;justify-content:flex-end;gap:12px;margin-top:20px">
        <button class="btn" :disabled="pagination.page <= 1" @click="changePage(-1)">上一页</button>
        <span style="align-self:center;color:#64748b;font-size:13px">第 {{ pagination.page }} / {{ totalPages }} 页</span>
        <button class="btn" :disabled="pagination.page >= totalPages" @click="changePage(1)">下一页</button>
      </div>
    </PanelCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import PanelCard from '../components/PanelCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { apiGet, apiPost } from '../composables/useApi'
import { getApiErrorMessage } from '../utils/apiError'
import { platformName, statusLabel, statusTone } from '../utils/status'

interface Account {
  id: number
  platform: string
  account_name: string
  profile_url: string
  platform_account_id: string | null
  check_interval: number
  is_enabled: boolean
  notification_enabled: boolean
  init_mode: string
  init_limit: number
  status: string
  error_message: string | null
  last_checked_at: string | null
  last_post_published_at: string | null
}

const loading = ref(true)
const accounts = ref<Account[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const filters = reactive({ platform: '', status: '', keyword: '' })
const actionLoading = ref<string | null>(null)
const feedback = reactive<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' })
let refreshTimer: number | null = null

const totalPages = computed(() => Math.max(1, Math.ceil(pagination.total / pagination.page_size)))

async function loadAccounts() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: pagination.page, page_size: pagination.page_size }
    if (filters.platform) params.platform = filters.platform
    if (filters.status) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword
    const res = await apiGet<any>('/accounts', params)
    accounts.value = res?.items ?? []
    if (res?.pagination) {
      pagination.page = res.pagination.page
      pagination.total = res.pagination.total
    }
  } catch (error) {
    showFeedback('error', getApiErrorMessage(error, '加载博主列表失败'))
  }
  loading.value = false
}

function changePage(delta: number) {
  pagination.page += delta
  loadAccounts()
}

function busyAction(id: number, action: string): boolean {
  return actionLoading.value === `${action}:${id}`
}

function showFeedback(type: 'success' | 'error', message: string) {
  feedback.type = type
  feedback.message = message
}

async function runAccountAction<T>(id: number, action: string, handler: () => Promise<T>) {
  actionLoading.value = `${action}:${id}`
  feedback.message = ''
  try {
    const result = await handler()
    await loadAccounts()
    return result
  } catch (error) {
    showFeedback('error', getApiErrorMessage(error))
    return null
  } finally {
    actionLoading.value = null
  }
}

async function checkNow(id: number) {
  const res = await runAccountAction<{ message?: string; task_id?: string }>(id, 'check', () => apiPost(`/accounts/${id}/check-now`))
  if (res) {
    showFeedback('success', `${res.message || '已提交立即检查任务'}${res.task_id ? `（任务 ${res.task_id}）` : ''}`)
    startTemporaryRefresh()
  }
}

async function reimportAccount(id: number) {
  const res = await runAccountAction<{ message?: string; task_id?: string }>(id, 'reimport', () => apiPost(`/accounts/${id}/reimport`))
  if (res) {
    showFeedback('success', `${res.message || '已提交历史导入任务'}${res.task_id ? `（任务 ${res.task_id}）` : ''}`)
  }
}

async function toggleAccount(acc: Account) {
  const nextEnabled = !acc.is_enabled
  const res = await runAccountAction<Account>(acc.id, 'toggle', () => apiPost(`/accounts/${acc.id}/${acc.is_enabled ? 'disable' : 'enable'}`))
  if (res) {
    showFeedback('success', `已${nextEnabled ? '启用' : '停用'} ${res.account_name}`)
  }
}

function initModeLabel(mode: string): string {
  const labels: Record<string, string> = { none: '不导入', recent: '最近 N 条', all: '全部历史' }
  return labels[mode] ?? mode
}

function fmtTime(ts: string): string {
  try {
    return new Date(ts).toLocaleString('zh-CN')
  } catch { return ts }
}

function nextCheckLabel(acc: Account): string {
  if (!acc.is_enabled || acc.status === 'disabled') return '已停用'
  if (!acc.last_checked_at) return '待调度'
  const nextTime = new Date(new Date(acc.last_checked_at).getTime() + acc.check_interval * 1000)
  const diffMs = nextTime.getTime() - Date.now()
  if (diffMs <= 0) return '即将检查'
  const diffMinutes = Math.ceil(diffMs / 60000)
  if (diffMinutes < 60) return `${diffMinutes} 分钟后`
  return fmtTime(nextTime.toISOString())
}

function startTemporaryRefresh() {
  if (refreshTimer !== null) window.clearInterval(refreshTimer)
  let remaining = 6
  refreshTimer = window.setInterval(async () => {
    remaining -= 1
    await loadAccounts()
    if (remaining <= 0 && refreshTimer !== null) {
      window.clearInterval(refreshTimer)
      refreshTimer = null
    }
  }, 3000)
}

onMounted(loadAccounts)

onBeforeUnmount(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer)
  }
})
</script>
