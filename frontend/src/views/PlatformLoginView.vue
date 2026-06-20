<template>
  <div class="page-stack">
    <PanelCard :title="`${platformLabel} 登录中转页`" subtitle="在这里扫描服务器浏览器里的登录二维码，并保存登录态">
      <p v-if="feedback.message" class="inline-feedback" :class="feedback.type">{{ feedback.message }}</p>
      <div class="login-session-box">
        <div v-if="screenshotUrl" class="login-screenshot-wrap remote-browser-frame">
          <img
            :src="screenshotUrl"
            alt="远程浏览器画面"
            class="login-screenshot remote-browser-screen"
            @click="clickRemoteBrowser"
          />
        </div>
        <div v-else class="empty-state" style="min-height:220px">
          {{ loading ? '正在加载登录截图…' : '暂无登录截图' }}
        </div>
        <p class="post-body" style="font-size:13px;margin:0;color:#64748b">
          {{ session?.message || '请用微博 App 扫描截图中的二维码，手机确认后点击“保存 session”。' }}
          <span v-if="session?.expires_at">有效期至 {{ fmtDate(session.expires_at) }}</span>
        </p>
        <p class="post-body" style="font-size:13px;margin:0;color:#2563eb">
          这不是普通截图：你可以直接点击上面的画面，系统会在服务器浏览器里执行同位置点击。
        </p>
        <p v-if="session?.error_message" style="color:#dc2626;font-size:13px;margin:0">
          {{ session.error_message }}
        </p>
      </div>
      <div style="display:flex;justify-content:flex-end;gap:12px;flex-wrap:wrap">
        <RouterLink class="btn" to="/connections">返回平台连接</RouterLink>
        <button class="btn" :disabled="loading || remoteClicking" @click="() => refreshScreenshot()">
          {{ loading ? '刷新中…' : '刷新画面' }}
        </button>
        <button class="btn primary" :disabled="saving" @click="saveSession">
          {{ saving ? '保存中…' : '我已扫码，保存 session' }}
        </button>
      </div>
    </PanelCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PanelCard from '../components/PanelCard.vue'
import { apiGet, apiPost } from '../composables/useApi'
import { api } from '../services/api'
import { getApiErrorMessage } from '../utils/apiError'

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

const route = useRoute()
const router = useRouter()
const platform = computed(() => String(route.params.platform || 'weibo'))
const sessionId = computed(() => String(route.params.sessionId || ''))
const platformLabel = computed(() => ({ weibo: '微博', xueqiu: '雪球' }[platform.value] || platform.value))

const session = ref<LoginSession | null>(null)
const screenshotUrl = ref<string | null>(null)
const loading = ref(false)
const saving = ref(false)
const remoteClicking = ref(false)
const feedback = reactive<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' })

async function loadSession(refreshImage = true) {
  if (!sessionId.value) return
  loading.value = true
  try {
    session.value = await apiGet<LoginSession>(`/connections/${platform.value}/login/${sessionId.value}`)
    if (refreshImage) await refreshScreenshot(false)
    if (session.value.status === 'success') {
      feedback.type = 'success'
      feedback.message = '登录态已保存，可以返回平台连接页继续检测。'
    } else if (session.value.status === 'failed' || session.value.status === 'expired') {
      feedback.type = 'error'
      feedback.message = session.value.error_message || session.value.message || '登录会话不可用，请重新生成登录链接。'
    }
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '加载登录会话失败')
  } finally {
    loading.value = false
  }
}

async function refreshScreenshot(showLoading = true) {
  if (!session.value?.screenshot_url) return
  if (showLoading) loading.value = true
  try {
    const { data } = await api.get(session.value.screenshot_url, {
      responseType: 'blob',
      params: { t: Date.now() },
    })
    cleanupScreenshotUrl()
    screenshotUrl.value = URL.createObjectURL(data)
  } catch (error) {
    if (showLoading) {
      feedback.type = 'error'
      feedback.message = getApiErrorMessage(error, '刷新登录截图失败')
    }
  } finally {
    if (showLoading) loading.value = false
  }
}

async function saveSession() {
  saving.value = true
  try {
    await loadSession(false)
    if (session.value?.status === 'success') {
      feedback.type = 'success'
      feedback.message = 'session 已保存，即将返回平台连接页。'
      setTimeout(() => router.push('/connections'), 1000)
    } else if (session.value?.status === 'failed' || session.value?.status === 'expired') {
      feedback.type = 'error'
      feedback.message = session.value.error_message || session.value.message || '保存失败，请重新生成登录链接。'
    } else {
      feedback.type = 'error'
      feedback.message = '还没有检测到可用登录态，请确认手机已完成登录后再保存。'
      await refreshScreenshot(false)
    }
  } finally {
    saving.value = false
  }
}

async function clickRemoteBrowser(event: MouseEvent) {
  if (!session.value || remoteClicking.value) return
  const image = event.currentTarget as HTMLImageElement
  const rect = image.getBoundingClientRect()
  const scaleX = image.naturalWidth / rect.width
  const scaleY = image.naturalHeight / rect.height
  const x = Math.round((event.clientX - rect.left) * scaleX)
  const y = Math.round((event.clientY - rect.top) * scaleY)

  remoteClicking.value = true
  feedback.type = 'success'
  feedback.message = '已发送点击到服务器浏览器，正在刷新画面…'
  try {
    session.value = await apiPost<LoginSession>(`/connections/${platform.value}/login/${session.value.id}/action`, {
      action: 'click',
      x,
      y,
    })
    await refreshScreenshot(false)
  } catch (error) {
    feedback.type = 'error'
    feedback.message = getApiErrorMessage(error, '远程点击失败')
  } finally {
    remoteClicking.value = false
  }
}

function cleanupScreenshotUrl() {
  if (screenshotUrl.value) {
    URL.revokeObjectURL(screenshotUrl.value)
    screenshotUrl.value = null
  }
}

function fmtDate(ts: string): string {
  try {
    return new Date(ts).toLocaleString('zh-CN')
  } catch {
    return ts
  }
}

onMounted(() => loadSession())
onBeforeUnmount(cleanupScreenshotUrl)
</script>
