<template>
  <div class="page-stack">
    <PanelCard :title="isEditMode ? '编辑监控博主' : '添加监控博主'" subtitle="配置平台、主页链接、检查频率和初始化导入策略">
      <div v-if="submitted" class="empty-state" style="min-height:120px;border-color:#16a34a;color:#16a34a">
        {{ isEditMode ? '博主保存成功！正在跳转到博主列表…' : '博主添加成功！正在跳转到博主列表…' }}
      </div>
      <div v-else-if="loading" class="empty-state" style="min-height:120px">正在加载博主信息…</div>
      <form v-else class="settings-grid" @submit.prevent="handleSubmit">
        <div class="field" style="grid-column:span 2">
          <label>名称 <span style="color:#dc2626">*</span></label>
          <input v-model="form.account_name" required placeholder="输入博主昵称 / 名称" />
        </div>
        <div class="field" style="grid-column:span 2">
          <label>主页链接 <span style="color:#dc2626">*</span></label>
          <input v-model="form.profile_url" required placeholder="https://weibo.com/u/123456 或 https://xueqiu.com/u/123456" />
        </div>
        <div class="field">
          <label>平台</label>
          <select v-model="form.platform" required :disabled="isEditMode">
            <option value="weibo">微博</option>
            <option value="xueqiu">雪球</option>
          </select>
          <span v-if="isEditMode" class="helper-note" style="margin:6px 0 0">编辑时不切换平台，避免旧归档内容混到另一平台。</span>
        </div>
        <div class="field">
          <label>平台账号 ID</label>
          <input v-model="form.platform_account_id" placeholder="微博 UID / 雪球用户 ID" />
        </div>
        <div class="field">
          <label>检查频率（秒）</label>
          <input v-model.number="form.check_interval" type="number" min="60" placeholder="300" />
        </div>
        <div class="field" style="grid-column:span 2;display:flex;align-items:center;justify-content:space-between">
          <div>
            <label>通知推送</label>
            <div class="helper-note" style="margin:4px 0 0">开启后，该博主的新内容、编辑和异常会推送到当前通知渠道。</div>
          </div>
          <ToggleSwitch v-model="form.notification_enabled" />
        </div>
        <div class="field">
          <label>初始化模式</label>
          <select v-model="form.init_mode">
            <option value="recent">最近 N 条</option>
            <option value="all">全部历史</option>
            <option value="none">不初始化</option>
          </select>
        </div>
        <div class="field" v-if="form.init_mode !== 'none'">
          <label>初始化数量</label>
          <input v-model.number="form.init_limit" type="number" min="1" placeholder="100" />
        </div>
        <div style="grid-column:span 2;display:flex;gap:12px;justify-content:flex-end">
          <RouterLink class="btn" to="/accounts">取消</RouterLink>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? (isEditMode ? '保存中…' : '添加中…') : (isEditMode ? '保存修改' : '添加博主') }}
          </button>
        </div>
        <p v-if="error" style="grid-column:span 2;color:#dc2626;font-size:13px;margin:0">{{ error }}</p>
      </form>
    </PanelCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PanelCard from '../components/PanelCard.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import { apiGet, apiPost, apiPut } from '../composables/useApi'

const router = useRouter()
const route = useRoute()
const accountId = computed(() => String(route.params.id || ''))
const isEditMode = computed(() => Boolean(accountId.value))

const form = reactive({
  platform: 'weibo',
  account_name: '',
  profile_url: '',
  platform_account_id: '',
  check_interval: 300,
  notification_enabled: false,
  init_mode: 'recent',
  init_limit: 100,
})

const loading = ref(false)
const submitting = ref(false)
const submitted = ref(false)
const error = ref<string | null>(null)

async function loadAccount() {
  if (!isEditMode.value) return
  loading.value = true
  error.value = null
  try {
    const account = await apiGet<any>(`/accounts/${accountId.value}`)
    form.platform = account.platform || 'weibo'
    form.account_name = account.account_name || ''
    form.profile_url = account.profile_url || ''
    form.platform_account_id = account.platform_account_id || ''
    form.check_interval = account.check_interval ?? 300
    form.notification_enabled = Boolean(account.notification_enabled)
    form.init_mode = account.init_mode || 'recent'
    form.init_limit = account.init_limit ?? 100
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载博主失败'
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  submitting.value = true
  error.value = null
  try {
    const body = {
      account_name: form.account_name,
      profile_url: form.profile_url,
      platform_account_id: form.platform_account_id || null,
      check_interval: form.check_interval,
      notification_enabled: form.notification_enabled,
      init_mode: form.init_mode,
      init_limit: form.init_limit,
    }
    if (isEditMode.value) {
      await apiPut(`/accounts/${accountId.value}`, body)
    } else {
      await apiPost('/accounts', {
        platform: form.platform,
        ...body,
      })
    }
    submitted.value = true
    setTimeout(() => router.push('/accounts'), 1500)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || (isEditMode.value ? '保存失败' : '添加失败')
  }
  submitting.value = false
}

onMounted(loadAccount)
</script>
