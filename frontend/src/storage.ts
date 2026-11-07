// localStorage может быть недоступен (приватный режим, запрет сайта) — не падаем.

export const storage = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value)
    } catch {
      /* ignore */
    }
  },
  remove(key: string) {
    try {
      localStorage.removeItem(key)
    } catch {
      /* ignore */
    }
  },
  getJSON<T>(key: string, fallback: T): T {
    const raw = storage.get(key)
    if (raw === null) return fallback
    try {
      return JSON.parse(raw) as T
    } catch {
      return fallback
    }
  },
  setJSON(key: string, value: unknown) {
    storage.set(key, JSON.stringify(value))
  },
}
