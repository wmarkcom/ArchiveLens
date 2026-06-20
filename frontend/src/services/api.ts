import axios from 'axios'

export const ADMIN_TOKEN_STORAGE_KEY = 'archivelens_admin_token'

export function getAdminToken(): string {
  return localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || import.meta.env.VITE_ADMIN_TOKEN || ''
}

export function hasAdminToken(): boolean {
  return Boolean(getAdminToken())
}

export function setAdminToken(token: string) {
  localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token)
}

export function clearAdminToken() {
  localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)
}

export const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = getAdminToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    if (status === 401 || status === 403) {
      window.dispatchEvent(new CustomEvent('archivelens:auth-required'))
    }
    return Promise.reject(error)
  },
)
