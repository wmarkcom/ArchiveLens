<template>
  <div class="page-stack">
    <PanelCard compact>
      <div class="filters-card">
        <div class="field">
          <label>平台</label>
          <select v-model="filters.platform" @change="loadMedia()">
            <option value="">全部平台</option>
            <option value="weibo">微博</option>
            <option value="xueqiu">雪球</option>
          </select>
        </div>
        <div class="field">
          <label>类型</label>
          <select v-model="filters.type" @change="loadMedia()">
            <option value="">全部类型</option>
            <option value="image">图片</option>
            <option value="video_cover">视频封面</option>
          </select>
        </div>
        <div class="field">
          <label>下载状态</label>
          <select v-model="filters.download_status" @change="loadMedia()">
            <option value="">全部状态</option>
            <option value="pending">等待中</option>
            <option value="downloading">下载中</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
          </select>
        </div>
        <div style="align-self:end">
          <button class="btn primary" :disabled="loading" @click="loadMedia()">{{ loading ? '刷新中…' : '刷新' }}</button>
        </div>
      </div>
    </PanelCard>

    <PanelCard title="媒体资源" subtitle="查看本地图片和视频封面下载状态">
      <p v-if="hasActiveDownloads" class="inline-hint">检测到下载中资源，页面每 3 秒自动刷新。</p>
      <p v-if="feedback.message" class="inline-feedback" :class="feedback.type">{{ feedback.message }}</p>
      <div v-if="assets.length === 0 && !loading" class="empty-state">暂无媒体资源</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:68px">平台</th>
              <th style="width:100px">类型</th>
              <th>原始 URL</th>
              <th>本地路径</th>
              <th style="width:80px">大小</th>
              <th style="width:90px">状态</th>
              <th style="width:70px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="asset in assets" :key="asset.id">
              <td><strong>{{ platformName(asset.platform) }}</strong></td>
              <td>{{ asset.asset_type === 'image' ? '图片' : '视频封面' }}</td>
              <td class="truncate" style="max-width:240px">{{ asset.original_url }}</td>
              <td class="truncate" style="max-width:200px">{{ asset.local_path || '-' }}</td>
              <td>{{ formatSize(asset.file_size) }}</td>
              <td><StatusBadge :tone="statusTone(asset.download_status)">{{ statusLabel(asset.download_status) }}</StatusBadge></td>
              <td>
                <button v-if="asset.download_status === 'failed'" class="btn text" :disabled="retryingId === asset.id" @click="retryDownload(asset.id)">
                  {{ retryingId === asset.id ? '提交中…' : '重试' }}
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

interface MediaAsset {
  id: number
  platform: string
  asset_type: string
  original_url: string
  local_path: string | null
  file_size: number | null
  download_status: string
}

const loading = ref(true)
const assets = ref<MediaAsset[]>([])
const filters = reactive({ platform: '', type: '', download_status: '' })
const retryingId = ref<number | null>(null)
const feedback = reactive<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' })
let refreshTimer: number | null = null

const hasActiveDownloads = computed(() => assets.value.some((asset) => ['pending', 'downloading'].includes(asset.download_status)))

async function loadMedia(options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true
  const params: Record<string, any> = { page_size: 50 }
  if (filters.platform) params.platform = filters.platform
  if (filters.type) params.asset_type = filters.type
  if (filters.download_status) params.download_status = filters.download_status
  try {
    const res = await apiGet<any>('/media', params)
    assets.value = res?.items ?? []
    if (!options.silent) feedback.message = ''
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '加载媒体资源失败')
  } finally {
    if (!options.silent) loading.value = false
  }
}

async function retryDownload(id: number) {
  retryingId.value = id
  feedback.message = ''
  try {
    const res = await apiPost<{ message?: string; task_id?: string }>(`/media/${id}/retry-download`)
    feedback.type = 'success'
    feedback.message = `${res.message || '媒体下载任务已重新排队'}${res.task_id ? `（任务 ${res.task_id}）` : ''}`
    await loadMedia()
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '重试媒体下载失败')
  } finally {
    retryingId.value = null
  }
}

function formatSize(bytes: number | null): string {
  if (bytes == null) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(() => {
  loadMedia()
  refreshTimer = window.setInterval(() => {
    if (hasActiveDownloads.value) {
      loadMedia({ silent: true })
    }
  }, 3000)
})

onBeforeUnmount(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer)
  }
})
</script>
