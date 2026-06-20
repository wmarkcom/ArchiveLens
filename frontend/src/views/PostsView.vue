<template>
  <div class="page-stack">
    <PanelCard compact>
      <div class="filters-card">
        <div class="field">
          <label>平台</label>
          <select v-model="filters.platform" @change="handlePlatformChange">
            <option value="">全部平台</option>
            <option value="weibo">微博</option>
            <option value="xueqiu">雪球</option>
          </select>
        </div>
        <div class="field">
          <label>博主</label>
          <select v-model.number="filters.account_id" @change="applyFilters">
            <option :value="0">全部博主</option>
            <option v-for="account in visibleAccounts" :key="account.id" :value="account.id">
              {{ account.account_name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>状态</label>
          <select v-model="filters.status" @change="applyFilters">
            <option value="">全部状态</option>
            <option value="normal">正常</option>
            <option value="edited">已编辑</option>
            <option value="deleted">已删除</option>
            <option value="hidden">不可见</option>
          </select>
        </div>
        <div class="field">
          <label>关键词</label>
          <input v-model="filters.keyword" placeholder="搜索正文 / 博主" @keyup.enter="applyFilters" />
        </div>
      </div>
    </PanelCard>

    <PanelCard title="内容归档列表" subtitle="搜索、筛选和查看已归档的正文、图片、视频封面">
      <div v-if="posts.length === 0 && !loading" class="empty-state">暂无匹配内容</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:68px">平台</th>
              <th style="width:100px">博主</th>
              <th>内容摘要</th>
              <th style="width:74px">状态</th>
              <th style="width:100px">采集时间</th>
              <th style="width:60px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="post in posts" :key="post.id">
              <td><strong>{{ platformName(post.platform) }}</strong></td>
              <td>{{ post.account_name }}</td>
              <td>
                <div class="post-summary-cell">
                  <img v-if="post.cover_url" class="post-thumb" :src="post.cover_url" alt="首图缩略图" loading="lazy" />
                  <div class="truncate">{{ post.full_text || post.title || '(无文字内容)' }}</div>
                </div>
              </td>
              <td><StatusBadge :tone="statusTone(post.status)">{{ statusLabel(post.status) }}</StatusBadge></td>
              <td>{{ post.last_collected_at ? fmtTime(post.last_collected_at) : '-' }}</td>
              <td><RouterLink class="btn text" :to="`/posts/${post.id}`">详情</RouterLink></td>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import PanelCard from '../components/PanelCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { apiGet } from '../composables/useApi'
import { platformName, statusLabel, statusTone } from '../utils/status'

interface PostItem {
  id: number
  platform: string
  account_name: string
  full_text: string | null
  title: string | null
  cover_url: string | null
  status: string
  last_collected_at: string
}

interface AccountOption {
  id: number
  platform: string
  account_name: string
}

const route = useRoute()
const loading = ref(true)
const posts = ref<PostItem[]>([])
const accounts = ref<AccountOption[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const filters = reactive({ platform: '', account_id: 0, status: '', keyword: '' })

const totalPages = computed(() => Math.max(1, Math.ceil(pagination.total / pagination.page_size)))
const visibleAccounts = computed(() => {
  if (!filters.platform) return accounts.value
  return accounts.value.filter((account) => account.platform === filters.platform)
})

async function loadAccounts() {
  try {
    const res = await apiGet<any>('/accounts', { page_size: 100 })
    accounts.value = res?.items ?? []
  } catch {}
}

async function loadPosts() {
  loading.value = true
  const params: Record<string, any> = { page: pagination.page, page_size: pagination.page_size }
  if (filters.platform) params.platform = filters.platform
  if (filters.account_id) params.account_id = filters.account_id
  if (filters.status) params.status = filters.status
  if (filters.keyword) params.keyword = filters.keyword
  try {
    const res = await apiGet<any>('/posts', params)
    posts.value = res?.items ?? []
    if (res?.pagination) {
      pagination.page = res.pagination.page
      pagination.total = res.pagination.total
    }
  } catch {}
  loading.value = false
}

function applyFilters() {
  pagination.page = 1
  loadPosts()
}

function handlePlatformChange() {
  if (filters.account_id && !visibleAccounts.value.some((account) => account.id === filters.account_id)) {
    filters.account_id = 0
  }
  applyFilters()
}

function changePage(delta: number) {
  pagination.page += delta
  loadPosts()
}

function fmtTime(ts: string): string {
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

onMounted(() => {
  if (route.query.keyword) filters.keyword = String(route.query.keyword)
  if (route.query.account_id) filters.account_id = Number(route.query.account_id) || 0
  loadAccounts()
  loadPosts()
})
</script>
