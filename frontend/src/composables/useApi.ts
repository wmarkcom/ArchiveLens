import { ref, type Ref } from 'vue'
import { api } from '../services/api'

export interface ApiState<T> {
  data: Ref<T | null>
  loading: Ref<boolean>
  error: Ref<string | null>
  refresh: () => Promise<void>
}

export function useApi<T>(fetcher: () => Promise<T>): ApiState<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref<string | null>(null)

  const refresh = async () => {
    loading.value = true
    error.value = null
    try {
      data.value = await fetcher()
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || '请求失败'
    } finally {
      loading.value = false
    }
  }

  refresh()
  return { data, loading, error, refresh }
}

export async function apiGet<T>(url: string, params?: Record<string, any>): Promise<T> {
  const { data } = await api.get(url, { params })
  return data
}

export async function apiPost<T>(url: string, body?: any): Promise<T> {
  const { data } = await api.post(url, body)
  return data
}

export async function apiPut<T>(url: string, body?: any): Promise<T> {
  const { data } = await api.put(url, body)
  return data
}

export async function apiDelete(url: string): Promise<any> {
  const { data } = await api.delete(url)
  return data
}
