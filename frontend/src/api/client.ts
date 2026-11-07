// Тонкая обёртка над fetch: токен, JSON, единый формат ошибок {"detail": "..."}.

export const API_URL: string = import.meta.env.VITE_API_URL ?? '/api/v1'

const TOKEN_KEY = 'labflow_token'

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* приватный режим — токен живёт до перезагрузки */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  },
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export async function api<T>(path: string, method: Method = 'GET', body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res: Response
  try {
    res = await fetch(API_URL + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Нет связи с сервером')
  }

  if (res.status === 204) return undefined as T
  const data: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in data ? String(data.detail) : res.statusText
    if (res.status === 401) window.dispatchEvent(new Event('labflow:unauthorized'))
    throw new ApiError(res.status, detail || 'Ошибка запроса')
  }
  return data as T
}

/** Адрес WebSocket очереди с учётом http/https и относительного API_URL. */
export function queueSocketUrl(queueId: number): string {
  const base = new URL(API_URL, window.location.href)
  const protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
  const path = base.pathname.replace(/\/$/, '')
  const token = encodeURIComponent(tokenStore.get() ?? '')
  return `${protocol}//${base.host}${path}/ws/queues/${queueId}?token=${token}`
}

export function errorText(err: unknown): string {
  return err instanceof Error ? err.message : 'Что-то пошло не так'
}
