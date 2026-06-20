export function getApiErrorMessage(error: unknown, fallback = '请求失败'): string {
  const anyError = error as { response?: { data?: { detail?: string } }; message?: string }
  return anyError?.response?.data?.detail || anyError?.message || fallback
}
