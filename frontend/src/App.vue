<template>
  <div class="app-shell">
    <aside class="sidebar">
      <RouterLink class="brand-block" to="/dashboard">
        <strong>ArchiveLens</strong>
        <span>单用户多平台博主内容监控归档</span>
      </RouterLink>
      <nav class="nav">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path">
          <span class="nav-dot">●</span>
          {{ item.label }}
          <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
        </RouterLink>
      </nav>
      <div class="runtime-card">
        <strong>运行模式</strong>
        <span>本地直连云库</span>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div>
          <h1>{{ pageTitle }}</h1>
          <p class="eyebrow">{{ pageSubtitle }}</p>
        </div>
        <div class="topbar-actions">
          <label class="global-search">
            <input v-model="searchQuery" placeholder="搜索内容 / 博主" @keyup.enter="handleSearch" />
          </label>
          <span class="avatar">A</span>
          <button class="btn text" @click="openTokenModal">{{ hasToken ? '更换 Token' : '填写 Token' }}</button>
        </div>
      </header>

      <main class="content">
        <div v-if="loading" class="loading-state">加载中…</div>
        <RouterView v-else v-slot="{ Component }">
          <component :is="Component" />
        </RouterView>
      </main>
    </div>

    <div v-if="showTokenModal" class="modal-backdrop">
      <div class="modal">
        <div class="panel-card token-card">
          <div class="panel-header">
            <div>
              <h2>填写后台访问 Token</h2>
              <p>请输入项目根目录 `.env` 里的 ADMIN_TOKEN，本地浏览器会保存到 localStorage。</p>
            </div>
          </div>
          <p v-if="tokenError" class="inline-feedback error">{{ tokenError }}</p>
          <label class="field">
            <span>ADMIN_TOKEN</span>
            <input v-model="tokenInput" type="password" placeholder="粘贴 ADMIN_TOKEN" @keyup.enter="saveToken" />
          </label>
          <div style="display:flex;justify-content:flex-end;gap:12px;margin-top:18px">
            <button v-if="hasToken" class="btn" @click="showTokenModal = false">取消</button>
            <button class="btn primary" :disabled="!tokenInput.trim()" @click="saveToken">保存并刷新</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearAdminToken, hasAdminToken, setAdminToken } from './services/api'

const navItems: { path: string; label: string; badge?: string }[] = [
  { path: '/dashboard', label: '总览' },
  { path: '/connections', label: '平台连接' },
  { path: '/accounts', label: '监控博主' },
  { path: '/import-jobs', label: '导入任务' },
  { path: '/posts', label: '内容归档' },
  { path: '/media', label: '媒体资源' },
  { path: '/notifications', label: '通知记录' },
  { path: '/worker-logs', label: '运行日志' },
  { path: '/settings', label: '系统设置' },
]

const route = useRoute()
const router = useRouter()
const searchQuery = ref('')
const hasToken = ref(hasAdminToken())
const showTokenModal = ref(!hasToken.value)
const tokenInput = ref('')
const tokenError = ref('')

const loading = ref(false)

const pageTitle = computed(() => String(route.meta.title ?? '总览'))
const pageSubtitle = computed(() => String(route.meta.subtitle ?? ''))

function handleSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  router.push({ path: '/posts', query: { keyword: q } })
}

function openTokenModal() {
  tokenInput.value = ''
  tokenError.value = ''
  showTokenModal.value = true
}

function saveToken() {
  const token = tokenInput.value.trim()
  if (!token) return
  setAdminToken(token)
  hasToken.value = true
  showTokenModal.value = false
  window.location.reload()
}

function handleAuthRequired() {
  clearAdminToken()
  hasToken.value = false
  tokenInput.value = ''
  tokenError.value = 'Token 无效或已过期，请重新填写。'
  showTokenModal.value = true
}

onMounted(() => {
  window.addEventListener('archivelens:auth-required', handleAuthRequired)
})

onBeforeUnmount(() => {
  window.removeEventListener('archivelens:auth-required', handleAuthRequired)
})
</script>

<style scoped>
.nav-badge {
  margin-left: auto;
  background: #dc2626;
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  padding: 2px 7px;
  border-radius: 999px;
}
.loading-state {
  display: grid;
  place-items: center;
  min-height: 200px;
  color: #94a3b8;
  font-size: 14px;
}
.token-card {
  padding: 24px;
}
.token-card h2 {
  margin: 0 0 6px;
}
.token-card p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}
</style>
