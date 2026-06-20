<template>
  <div class="page-stack">
    <PanelCard compact>
      <div class="filters-card">
        <div class="field">
          <label>Worker</label>
          <select v-model="filters.worker_name" @change="loadLogs()">
            <option value="">全部 Worker</option>
            <option value="monitor">监控</option>
            <option value="import">导入</option>
            <option value="media">媒体</option>
          </select>
        </div>
        <div class="field">
          <label>任务</label>
          <select v-model="filters.task_name" @change="loadLogs()">
            <option value="">全部任务</option>
            <option value="monitor.scan_due_accounts">扫描到期账号</option>
            <option value="monitor.check_account">检查账号</option>
            <option value="import.run_job">历史导入</option>
            <option value="media.download_asset">媒体下载</option>
          </select>
        </div>
        <div class="field">
          <label>状态</label>
          <select v-model="filters.status" @change="loadLogs()">
            <option value="">全部状态</option>
            <option value="running">运行中</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
          </select>
        </div>
        <div style="align-self:end">
          <button class="btn primary" :disabled="loading" @click="loadLogs()">{{ loading ? '刷新中…' : '刷新' }}</button>
        </div>
      </div>
    </PanelCard>

    <PanelCard title="Worker 运行日志" subtitle="查看定时扫描、账号检查、历史导入和媒体下载的执行记录">
      <p v-if="hasRunningLogs" class="inline-hint">检测到运行中任务，页面每 3 秒自动刷新。</p>
      <p v-if="feedback.message" class="inline-feedback" :class="feedback.type">{{ feedback.message }}</p>
      <div v-if="logs.length === 0 && !loading" class="empty-state">暂无运行日志</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:82px">Worker</th>
              <th style="width:150px">任务</th>
              <th style="width:80px">状态</th>
              <th style="width:90px">耗时</th>
              <th>结果摘要</th>
              <th style="width:140px">开始时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td><strong>{{ workerLabel(log.worker_name) }}</strong></td>
              <td>{{ taskLabel(log.task_name) }}</td>
              <td><StatusBadge :tone="statusTone(log.status)">{{ statusLabel(log.status) }}</StatusBadge></td>
              <td>{{ formatDuration(log.duration_ms) }}</td>
              <td>
                <div class="truncate" :title="summaryTitle(log)">
                  {{ summaryText(log) }}
                </div>
                <div v-if="log.error_message" class="truncate" style="font-size:12px;color:#dc2626" :title="log.error_message">
                  {{ log.error_message }}
                </div>
              </td>
              <td>{{ fmtTime(log.started_at) }}</td>
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
import { apiGet } from '../composables/useApi'
import { getApiErrorMessage } from '../utils/apiError'
import { statusLabel, statusTone } from '../utils/status'

interface WorkerLog {
  id: number
  worker_name: string
  task_name: string
  status: string
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  error_message: string | null
  payload: Record<string, any>
}

const loading = ref(true)
const logs = ref<WorkerLog[]>([])
const pagination = reactive({ page: 1, page_size: 50, total: 0 })
const filters = reactive({ worker_name: '', task_name: '', status: '' })
const feedback = reactive<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' })
let refreshTimer: number | null = null

const totalPages = computed(() => Math.max(1, Math.ceil(pagination.total / pagination.page_size)))
const hasRunningLogs = computed(() => logs.value.some((log) => log.status === 'running'))

async function loadLogs(options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true
  const params: Record<string, any> = { page: pagination.page, page_size: pagination.page_size }
  if (filters.worker_name) params.worker_name = filters.worker_name
  if (filters.task_name) params.task_name = filters.task_name
  if (filters.status) params.status = filters.status
  try {
    const res = await apiGet<any>('/worker-logs', params)
    logs.value = res?.items ?? []
    if (res?.pagination) {
      pagination.page = res.pagination.page
      pagination.total = res.pagination.total
    }
    if (!options.silent) feedback.message = ''
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '加载运行日志失败')
  } finally {
    if (!options.silent) loading.value = false
  }
}

function changePage(delta: number) {
  pagination.page += delta
  loadLogs()
}

function workerLabel(worker: string): string {
  const labels: Record<string, string> = { monitor: '监控', import: '导入', media: '媒体' }
  return labels[worker] ?? worker
}

function taskLabel(task: string): string {
  const labels: Record<string, string> = {
    'monitor.scan_due_accounts': '扫描到期账号',
    'monitor.check_account': '检查账号',
    'import.run_job': '历史导入',
    'media.download_asset': '媒体下载',
  }
  return labels[task] ?? task
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function summaryText(log: WorkerLog): string {
  const result = log.payload?.result
  if (!result) return JSON.stringify(log.payload || {})
  if (log.task_name === 'monitor.scan_due_accounts') {
    return `扫描 ${result.scanned ?? 0}，排队 ${result.enqueued ?? 0}，跳过锁 ${result.skipped_locked ?? 0}`
  }
  if (log.task_name === 'monitor.check_account') {
    return `账号 ${result.account_id ?? '-'}，新增 ${result.new_posts ?? 0}，编辑 ${result.edited_posts ?? 0}，媒体任务 ${result.queued_media_tasks ?? 0}`
  }
  if (log.task_name === 'import.run_job') {
    return `任务 ${result.job_id ?? '-'}，处理 ${result.processed ?? 0}，失败 ${result.failed ?? 0}，媒体任务 ${result.queued_media_tasks ?? 0}`
  }
  if (log.task_name === 'media.download_asset') {
    return `资源 ${result.asset_id ?? '-'}，${result.local_path || result.status || '-'}`
  }
  return JSON.stringify(result)
}

function summaryTitle(log: WorkerLog): string {
  return JSON.stringify(log.payload || {}, null, 2)
}

function fmtTime(ts: string): string {
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

onMounted(() => {
  loadLogs()
  refreshTimer = window.setInterval(() => {
    if (hasRunningLogs.value) {
      loadLogs({ silent: true })
    }
  }, 3000)
})

onBeforeUnmount(() => {
  if (refreshTimer !== null) window.clearInterval(refreshTimer)
})
</script>
