<template>
  <div class="page-stack">
    <PanelCard title="系统配置" subtitle="配置采集频率、媒体归档、推送渠道和安全策略">
      <div v-if="loading" class="empty-state">加载中…</div>
      <form v-else class="settings-grid" @submit.prevent="saveSettings">
        <div class="field" style="grid-column:span 2">
          <label>通知渠道</label>
          <select v-model="form.notification_channel">
            <option value="feishu">飞书</option>
            <option value="wecom">企业微信</option>
          </select>
        </div>
        <div class="field">
          <label>飞书 Webhook URL</label>
          <input v-model="form.webhook_feishu_url" type="url" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..." />
        </div>
        <div class="field">
          <label>企业微信 Webhook URL</label>
          <input v-model="form.webhook_wecom_url" type="url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
        </div>
        <div class="field">
          <label>默认检查间隔（秒）</label>
          <input v-model.number="form.default_check_interval" type="number" min="60" placeholder="300" />
        </div>
        <div class="field">
          <label>媒体存储根目录</label>
          <input v-model="form.media_root" placeholder="/data/media" readonly />
        </div>
        <div style="grid-column:span 2;display:flex;gap:12px;justify-content:flex-end">
          <button class="btn" type="button" @click="loadSettings">重置</button>
          <button class="btn primary" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存设置' }}</button>
        </div>
        <p v-if="msg" style="grid-column:span 2;color:#16a34a;font-size:13px;margin:0">{{ msg }}</p>
        <p v-if="error" style="grid-column:span 2;color:#dc2626;font-size:13px;margin:0">{{ error }}</p>
      </form>
    </PanelCard>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import PanelCard from '../components/PanelCard.vue'
import { apiGet, apiPut } from '../composables/useApi'

const loading = ref(true)
const saving = ref(false)
const msg = ref<string | null>(null)
const error = ref<string | null>(null)
const form = reactive<Record<string, string | number>>({
  notification_channel: 'feishu',
  webhook_feishu_url: '',
  webhook_wecom_url: '',
  default_check_interval: 300,
  media_root: '/data/media',
})

async function loadSettings() {
  loading.value = true
  error.value = null
  try {
    const items = await apiGet<any[]>('/settings')
    for (const item of items) {
      const formKey = settingKeyToFormKey(item.key)
      if (formKey in form) {
        form[formKey] = item.value_type === 'number' ? Number(item.value) : (item.value ?? '')
      }
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '加载设置失败'
  }
  loading.value = false
}

async function saveSettings() {
  saving.value = true
  msg.value = null
  error.value = null
  try {
    const settings = Object.entries(form).map(([key, value]) => ({
      key: formKeyToSettingKey(key),
      value: String(value),
    }))
    await apiPut('/settings', { settings })
    msg.value = '设置已保存'
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '保存失败'
  }
  saving.value = false
}

function settingKeyToFormKey(key: string): string {
  const aliases: Record<string, string> = {
    feishu_webhook: 'webhook_feishu_url',
    wecom_webhook: 'webhook_wecom_url',
  }
  return aliases[key] ?? key
}

function formKeyToSettingKey(key: string): string {
  const aliases: Record<string, string> = {
    webhook_feishu_url: 'webhook_feishu_url',
    webhook_wecom_url: 'webhook_wecom_url',
  }
  return aliases[key] ?? key
}

onMounted(loadSettings)
</script>
