<template>
  <div class="page-stack">
    <p v-if="feedback.message" class="inline-feedback" :class="feedback.type">{{ feedback.message }}</p>
    <section class="cards-grid">
      <PanelCard v-for="conn in connections" :key="conn.platform" :title="platformLabels[conn.platform] + ' 连接'" subtitle="平台授权登录态管理">
        <div class="connection-card">
          <div class="connection-head">
            <div class="connection-title">
              <strong>{{ conn.platform }}.com</strong>
              <span>上次登录：{{ conn.last_login_at ? fmtDate(conn.last_login_at) : '从未' }}</span>
            </div>
            <StatusBadge :tone="connStatusTone(conn.status)">{{ connStatusLabel(conn.status) }}</StatusBadge>
          </div>
          <div class="settings-row">
            <span>登录态文件</span>
            <StatusBadge :tone="authStateTone(conn.auth_state)">
              {{ authStateLabel(conn.auth_state) }}
            </StatusBadge>
          </div>
          <div class="settings-row">
            <span>文件信息</span>
            <strong>{{ authStateMeta(conn.auth_state) }}</strong>
          </div>
          <div class="settings-row" v-if="conn.auth_state?.message">
            <span>状态说明</span>
            <strong :style="{ color: conn.auth_state.has_required_cookie ? '#16a34a' : '#d97706' }">
              {{ conn.auth_state.message }}
            </strong>
          </div>
          <div class="settings-row" v-if="conn.error_message">
            <span>错误信息</span>
            <strong style="color:#dc2626">{{ conn.error_message }}</strong>
          </div>
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <button class="btn primary" @click="refresh(conn.platform)" :disabled="refreshing === conn.platform">
              {{ refreshing === conn.platform ? '检测中…' : '重新检测' }}
            </button>
            <label class="btn" :class="{ disabled: uploading === conn.platform }">
              {{ uploading === conn.platform ? '上传中…' : '上传登录态 JSON' }}
              <input type="file" accept="application/json,.json" style="display:none" :disabled="uploading === conn.platform" @change="uploadAuthState(conn.platform, $event)" />
            </label>
            <button class="btn" @click="generateLoginLink(conn.platform)" :disabled="loginStarting === conn.platform">
              {{ loginStarting === conn.platform ? '生成中…' : '生成登录链接' }}
            </button>
            <button class="btn danger" @click="logoutPlatform(conn.platform)">解绑</button>
          </div>
        </div>
      </PanelCard>
    </section>

    <div v-if="loginLinkModal" class="modal-backdrop" @click.self="closeLoginLinkModal">
      <div class="modal">
        <PanelCard :title="loginModalLabels[loginLinkModal] + ' 登录链接'" subtitle="复制链接到浏览器，完成扫码并保存 session">
          <p class="post-body" style="margin-top:0">
            系统已经在服务器上创建了一个临时浏览器登录会话。复制下面的链接到浏览器打开，
            扫码完成后在页面里点击“保存 session”。
          </p>
          <div class="field" style="margin:18px 0">
            <label>登录链接</label>
            <input :value="loginLink" readonly @focus="($event.target as HTMLInputElement).select()" />
          </div>
          <p class="post-body" style="font-size:13px;margin:0 0 18px;color:#64748b">
            链接有效期约 10 分钟。保存前后端会验证平台登录态；如果不可用，不会覆盖现有
            <strong>auth/{{ loginLinkModal }}.json</strong>。
          </p>
          <div style="display:flex;justify-content:flex-end;gap:12px;flex-wrap:wrap">
            <button class="btn" @click="closeLoginLinkModal">关闭</button>
            <button class="btn" @click="copyLoginLink">复制链接</button>
            <button class="btn primary" @click="openLoginLink">打开链接</button>
          </div>
        </PanelCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import PanelCard from '../components/PanelCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { apiGet, apiPost } from '../composables/useApi'
import { api } from '../services/api'
import { getApiErrorMessage } from '../utils/apiError'
import type { StatusTone } from '../data/mock'

interface AuthState {
  platform: string
  exists: boolean
  filename: string
  size_bytes: number | null
  updated_at: string | null
  cookie_count: number
  has_required_cookie: boolean
  message: string | null
}

interface Connection {
  id: number
  platform: string
  status: string
  session_data_encrypted: string | null
  auth_state: AuthState | null
  last_login_at: string | null
  error_message: string | null
}

interface LoginSession {
  id: string
  platform: string
  status: string
  login_url: string | null
  expires_at: string | null
  screenshot_url: string | null
  message: string | null
  error_message: string | null
}

const platformLabels: Record<string, string> = { weibo: '微博', xueqiu: '雪球' }
const loginModalLabels: Record<string, string> = { weibo: '微博', xueqiu: '雪球' }

const connections = ref<Connection[]>([])
const refreshing = ref<string | null>(null)
const uploading = ref<string | null>(null)
const loginStarting = ref<string | null>(null)
const loginLinkModal = ref<string | null>(null)
const loginSession = ref<LoginSession | null>(null)
const loginLink = ref('')
const feedback = reactive<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' })

function connStatusTone(status: string): StatusTone {
  if (status === 'connected') return 'green'
  if (status === 'expired' || status === 'failed') return 'red'
  if (status === 'pending_login') return 'yellow'
  return 'slate'
}

function connStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    connected: '已登录',
    disconnected: '未连接',
    pending_login: '等待登录',
    expired: '已过期',
    failed: '失败',
  }
  return labels[status] ?? status
}

function authStateTone(authState: AuthState | null): StatusTone {
  if (!authState?.exists) return 'slate'
  return authState.has_required_cookie ? 'green' : 'yellow'
}

function authStateLabel(authState: AuthState | null): string {
  if (!authState?.exists) return '未上传'
  if (authState.has_required_cookie) return `${authState.filename} 可用`
  return `${authState.filename} 待确认`
}

function authStateMeta(authState: AuthState | null): string {
  if (!authState?.exists) return '无文件'
  const size = formatSize(authState.size_bytes)
  const updatedAt = authState.updated_at ? fmtDate(authState.updated_at) : '-'
  return `${size} / ${authState.cookie_count} 个 cookie / ${updatedAt}`
}

function formatSize(size: number | null): string {
  if (size == null) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

async function loadConnections() {
  const res = await apiGet<any>('/connections')
  connections.value = res?.items ?? []
}

async function refresh(platform: string) {
  refreshing.value = platform
  try {
    await apiPost(`/connections/${platform}/refresh`)
    feedback.type = 'success'
    feedback.message = `${platformLabels[platform]} 登录态检测完成`
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '登录态检测失败')
  }
  await loadConnections()
  refreshing.value = null
}

async function logoutPlatform(platform: string) {
  try {
    await apiPost(`/connections/${platform}/logout`)
    feedback.type = 'success'
    feedback.message = `${platformLabels[platform]} 已解绑，并删除本地登录态文件`
    await loadConnections()
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '解绑失败')
  }
}

async function uploadAuthState(platform: string, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  const form = new FormData()
  form.append('file', file)
  uploading.value = platform
  try {
    await api.post(`/connections/${platform}/auth-state`, form)
    feedback.type = 'success'
    feedback.message = `${platformLabels[platform]} 登录态已上传，请点击“重新检测”确认是否有效`
    await loadConnections()
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '上传登录态失败')
  } finally {
    uploading.value = null
  }
}

async function generateLoginLink(platform: string) {
  loginStarting.value = platform
  try {
    loginSession.value = await apiPost<LoginSession>(`/connections/${platform}/login`)
    loginLink.value = `${window.location.origin}/platform-login/${platform}/${loginSession.value.id}`
    loginLinkModal.value = platform
    feedback.type = 'success'
    feedback.message = `${platformLabels[platform]} 登录链接已生成`
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '生成登录链接失败')
  } finally {
    loginStarting.value = null
  }
}

function closeLoginLinkModal() {
  loginLinkModal.value = null
  loginSession.value = null
  loginLink.value = ''
}

async function copyLoginLink() {
  try {
    await navigator.clipboard.writeText(loginLink.value)
    feedback.type = 'success'
    feedback.message = '登录链接已复制'
  } catch {
    feedback.type = 'error'
    feedback.message = '复制失败，请手动选中链接复制'
  }
}

function openLoginLink() {
  if (loginLink.value) window.open(loginLink.value, '_blank', 'noopener,noreferrer')
}

function fmtDate(ts: string): string {
  try {
    return new Date(ts).toLocaleString('zh-CN')
  } catch {
    return ts
  }
}

onMounted(loadConnections)
</script>
