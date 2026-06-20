<template>
  <div class="page-stack">
    <PanelCard compact>
      <div class="filters-card">
        <div class="field">
          <label>账号</label>
          <select v-model="filters.account_id" @change="loadJobs()">
            <option :value="0">全部账号</option>
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.account_name }}</option>
          </select>
        </div>
        <div class="field">
          <label>状态</label>
          <select v-model="filters.status" @change="loadJobs()">
            <option value="">全部状态</option>
            <option value="pending">等待中</option>
            <option value="running">运行中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="paused">已暂停</option>
          </select>
        </div>
        <div style="align-self:end">
          <button class="btn primary" :disabled="loading" @click="loadJobs()">{{ loading ? '刷新中…' : '刷新' }}</button>
        </div>
      </div>
    </PanelCard>

    <PanelCard title="导入任务" subtitle="查看历史内容导入进度、失败原因和重试状态">
      <p v-if="hasActiveJobs" class="inline-hint">检测到运行中任务，页面每 3 秒自动刷新。</p>
      <p v-if="feedback.message" class="inline-feedback" :class="feedback.type">{{ feedback.message }}</p>
      <div v-if="jobs.length === 0 && !loading" class="empty-state">暂无导入任务</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>账号</th>
              <th style="width:86px">平台</th>
              <th style="width:100px">模式</th>
              <th style="width:140px">进度</th>
              <th style="width:80px">状态</th>
              <th style="width:100px">更新时间</th>
              <th style="width:80px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id">
              <td><strong>{{ job.account_name }}</strong></td>
              <td><strong>{{ platformName(job.platform) }}</strong></td>
              <td>{{ initModeLabel(job.init_mode) }}</td>
              <td>
                <div class="progress" v-if="job.total_posts > 0">
                  <span :style="{ width: progressPercent(job) + '%' }" />
                </div>
                <span style="font-size:12px;color:#64748b">
                  {{ processedPosts(job) }} / {{ job.total_posts }}
                  <span v-if="job.failed_posts > 0" style="color:#dc2626">，失败 {{ job.failed_posts }}</span>
                </span>
                <div v-if="job.error_message" class="truncate" style="max-width:180px;font-size:12px;color:#dc2626" :title="job.error_message">
                  {{ job.error_message }}
                </div>
              </td>
              <td><StatusBadge :tone="statusTone(job.status)">{{ statusLabel(job.status) }}</StatusBadge></td>
              <td>{{ job.updated_at ? fmtTime(job.updated_at) : '-' }}</td>
              <td>
                <button v-if="['failed','paused','cancelled'].includes(job.status)" class="btn text" :disabled="retryingId === job.id" @click="retryJob(job.id)">
                  {{ retryingId === job.id ? '提交中…' : '重试' }}
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import PanelCard from '../components/PanelCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { apiGet, apiPost } from '../composables/useApi'
import { getApiErrorMessage } from '../utils/apiError'
import { platformName, statusLabel, statusTone } from '../utils/status'

interface ImportJob {
  id: number
  account_id: number
  platform: string
  account_name: string
  init_mode: string
  init_limit: number
  status: string
  total_posts: number
  imported_posts: number
  failed_posts: number
  cursor: string | null
  error_message: string | null
  updated_at: string | null
}

interface Account { id: number; account_name: string }

const loading = ref(true)
const jobs = ref<ImportJob[]>([])
const accounts = ref<Account[]>([])
const filters = reactive({ account_id: 0, status: '' })
const retryingId = ref<number | null>(null)
const feedback = reactive<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' })
let refreshTimer: number | null = null

const hasActiveJobs = computed(() => jobs.value.some((job) => ['pending', 'running'].includes(job.status)))

async function loadAccounts() {
  try {
    const res = await apiGet<any>('/accounts', { page_size: 100 })
    accounts.value = res?.items ?? []
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '加载账号列表失败')
  }
}

async function loadJobs(options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true
  const params: Record<string, any> = { page_size: 50 }
  if (filters.account_id) params.account_id = filters.account_id
  if (filters.status) params.status = filters.status
  try {
    const res = await apiGet<any>('/import-jobs', params)
    jobs.value = res?.items ?? []
    if (!options.silent) feedback.message = ''
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '加载导入任务失败')
  } finally {
    if (!options.silent) loading.value = false
  }
}

async function retryJob(id: number) {
  retryingId.value = id
  feedback.message = ''
  try {
    const res = await apiPost<{ message?: string; task_id?: string }>(`/import-jobs/${id}/retry`)
    feedback.type = 'success'
    feedback.message = `${res.message || '导入任务已重新排队'}${res.task_id ? `（任务 ${res.task_id}）` : ''}`
    await loadJobs()
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '重试导入任务失败')
  } finally {
    retryingId.value = null
  }
}

function initModeLabel(mode: string): string {
  const labels: Record<string, string> = { none: '不导入', recent: '最近 N 条', all: '全部历史' }
  return labels[mode] ?? mode
}

function processedPosts(job: ImportJob): number {
  return Math.min(job.total_posts, job.imported_posts + job.failed_posts)
}

function progressPercent(job: ImportJob): number {
  if (job.total_posts <= 0) return 0
  return Math.min(100, Math.round(processedPosts(job) / job.total_posts * 100))
}

function fmtTime(ts: string): string {
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

onMounted(async () => {
  await loadAccounts()
  await loadJobs()
  refreshTimer = window.setInterval(() => {
    if (hasActiveJobs.value) {
      loadJobs({ silent: true })
    }
  }, 3000)
})

onBeforeUnmount(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer)
  }
})
</script>
