<template>
  <div class="page-stack">
    <div v-if="loading" class="empty-state">加载中…</div>
    <template v-else-if="post">
      <div class="post-detail-grid">
        <div>
          <PanelCard title="正文内容" subtitle="原始采集文本">
            <div class="post-body" style="white-space:pre-wrap">{{ post.full_text || '(无正文内容)' }}</div>
            <div v-if="post.repost_text" style="margin-top:24px;border-left:3px solid #e2e8f0;padding-left:16px;color:#64748b;font-size:13px">
              <strong style="color:#0f172a">转发内容</strong>
              <p>{{ post.repost_text }}</p>
            </div>
            <div style="margin-top:24px">
              <a :href="post.original_url" target="_blank" class="btn" style="text-decoration:none">查看原文 ↗</a>
            </div>
          </PanelCard>

          <PanelCard v-if="imageAssets.length > 0" title="图片" subtitle="已优先展示本地归档文件" style="margin-top:28px">
            <div class="post-media-grid">
              <a
                v-for="asset in imageAssets"
                :key="asset.id"
                class="post-media-card"
                :href="asset.local_url || asset.original_url"
                target="_blank"
              >
                <img :src="asset.local_url || asset.original_url" :alt="`图片 ${asset.sort_order + 1}`" loading="lazy" />
                <span>{{ asset.download_status === 'success' ? formatSize(asset.file_size) : statusLabel(asset.download_status) }}</span>
              </a>
            </div>
          </PanelCard>

          <PanelCard v-if="snapshots.length > 0" title="历史快照" subtitle="已检测到的编辑版本" style="margin-top:28px">
            <div class="table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th style="width:80px">版本</th>
                    <th>正文摘要</th>
                    <th style="width:140px">采集时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="sn in snapshots" :key="sn.id">
                    <td><strong>v{{ sn.version }}</strong></td>
                    <td class="truncate">{{ (sn.full_text || '').substring(0, 120) }}</td>
                    <td>{{ sn.captured_at ? fmtTime(sn.captured_at) : '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </PanelCard>
        </div>

        <div>
          <PanelCard title="元数据" compact>
            <div class="settings-row">
              <span>平台</span>
              <strong>{{ platformName(post.platform) }}</strong>
            </div>
            <div class="settings-row">
              <span>博主</span>
              <strong>{{ post.account_name }}</strong>
            </div>
            <div class="settings-row">
              <span>发布时间</span>
              <strong>{{ post.published_at ? fmtTime(post.published_at) : '-' }}</strong>
            </div>
            <div class="settings-row">
              <span>状态</span>
              <StatusBadge :tone="statusTone(post.status)">{{ statusLabel(post.status) }}</StatusBadge>
            </div>
            <div class="settings-row">
              <span>编辑次数</span>
              <strong>{{ post.edit_count || 0 }}</strong>
            </div>
            <div class="settings-row">
              <span>采集时间</span>
              <strong>{{ fmtTime(post.last_collected_at) }}</strong>
            </div>
            <div class="settings-row">
              <span>来源</span>
              <strong>{{ post.source || '-' }}</strong>
            </div>
          </PanelCard>

          <PanelCard v-if="videoCoverAssets.length > 0" title="视频封面" compact style="margin-top:28px">
            <div class="media-strip">
              <a
                v-for="asset in videoCoverAssets"
                :key="asset.id"
                class="media-thumb"
                :href="asset.local_url || asset.original_url"
                target="_blank"
              >
                <img v-if="asset.local_url || asset.original_url" :src="asset.local_url || asset.original_url" :alt="`封面 ${asset.sort_order + 1}`" loading="lazy" />
                <span>封面 {{ asset.sort_order + 1 }}</span>
              </a>
            </div>
          </PanelCard>
        </div>
      </div>
    </template>
    <div v-else class="empty-state">内容不存在</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import PanelCard from '../components/PanelCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { apiGet } from '../composables/useApi'
import { platformName, statusLabel, statusTone } from '../utils/status'

interface PostDetail {
  id: number
  platform: string
  account_id: number
  account_name: string
  platform_post_id: string
  original_url: string
  published_at: string | null
  title: string | null
  full_text: string | null
  repost_text: string | null
  image_urls: string[]
  video_cover_urls: string[]
  media_assets: MediaAsset[]
  source: string | null
  content_hash: string | null
  is_edited: boolean
  edit_count: number
  status: string
  last_collected_at: string
}

interface MediaAsset {
  id: number
  asset_type: string
  original_url: string
  local_url: string | null
  file_size: number | null
  download_status: string
  sort_order: number
}

interface Snapshot {
  id: number
  version: number
  full_text: string | null
  captured_at: string | null
}

const route = useRoute()
const loading = ref(true)
const post = ref<PostDetail | null>(null)
const snapshots = ref<Snapshot[]>([])

const imageAssets = computed(() => post.value?.media_assets.filter((asset) => asset.asset_type === 'image') ?? [])
const videoCoverAssets = computed(() => post.value?.media_assets.filter((asset) => asset.asset_type === 'video_cover') ?? [])

async function loadDetail() {
  const id = route.params.id as string
  try {
    const [postData, snapData] = await Promise.all([
      apiGet<PostDetail>(`/posts/${id}`),
      apiGet<Snapshot[]>(`/posts/${id}/snapshots`),
    ])
    post.value = postData
    snapshots.value = snapData
  } catch {}
  loading.value = false
}

function fmtTime(ts: string): string {
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

function formatSize(bytes: number | null): string {
  if (bytes == null) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(loadDetail)
</script>
