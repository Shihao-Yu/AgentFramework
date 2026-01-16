import { getGlobalConfig } from '@/AppContext'

function getApiUrl(): string {
  const config = getGlobalConfig()
  if (config.apiBaseUrl) {
    return config.apiBaseUrl
  }
  return import.meta.env.VITE_API_URL || 'http://localhost:8000'
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | string[] | undefined>
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const apiUrl = getApiUrl()
  const url = new URL(path, apiUrl)
  
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined) return
      if (Array.isArray(value)) {
        value.forEach(v => url.searchParams.append(key, v))
      } else {
        url.searchParams.set(key, String(value))
      }
    })
  }
  
  return url.toString()
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, ...fetchOptions } = options
  const url = buildUrl(path, params)
  
  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      'Content-Type': 'application/json',
      ...fetchOptions.headers,
    },
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(error.message || `HTTP ${response.status}`)
  }
  
  return response.json()
}

export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
