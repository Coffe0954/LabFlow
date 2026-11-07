import { useCallback, useEffect, useRef, useState } from 'react'
import type { Entry } from '../api/types'
import { storage } from '../storage'

const KEY = 'labflow_alerts'

/** Короткий двойной сигнал через Web Audio — без файлов и библиотек. */
function beep() {
  try {
    const Ctx =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    const ctx = new Ctx()
    ;[0, 0.25].forEach((offset) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.frequency.value = 880
      gain.gain.setValueAtTime(0.0001, ctx.currentTime + offset)
      gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + offset + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + offset + 0.2)
      osc.connect(gain).connect(ctx.destination)
      osc.start(ctx.currentTime + offset)
      osc.stop(ctx.currentTime + offset + 0.22)
    })
    setTimeout(() => ctx.close(), 800)
  } catch {
    /* звук недоступен — не страшно */
  }
}

function showNotification(title: string, body: string) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return
  try {
    const n = new Notification(title, { body, tag: 'labflow-call', requireInteraction: true })
    n.onclick = () => {
      window.focus()
      n.close()
    }
  } catch {
    /* на некоторых телефонах уведомления доступны только из service worker */
  }
}

/**
 * Оповещения студента: «вы следующий» и «вас вызвали».
 * Звук + вибрация + системное уведомление + мигающий заголовок вкладки.
 */
export function useCallAlert(mine: Entry | undefined, queueTitle: string) {
  const [enabled, setEnabled] = useState(() => storage.get(KEY) !== 'off')
  const prev = useRef<{ status?: string; position?: number | null }>({})

  const toggle = useCallback(async () => {
    const next = !enabled
    if (next && 'Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission()
    }
    if (next) beep() // заодно «разблокируем» звук после действия пользователя
    setEnabled(next)
    storage.set(KEY, next ? 'on' : 'off')
  }, [enabled])

  useEffect(() => {
    const before = prev.current
    prev.current = { status: mine?.status, position: mine?.position }
    if (!enabled || !mine || before.status === undefined) return

    const called = before.status === 'waiting' && mine.status === 'called'
    const next = mine.status === 'waiting' && mine.position === 1 && before.position !== 1
    if (!called && !next) return

    beep()
    navigator.vibrate?.(called ? [300, 150, 300, 150, 300] : [200])
    showNotification(
      called ? 'Вас вызвали!' : 'Вы следующий',
      called ? `${queueTitle}: подходите к преподавателю` : `${queueTitle}: приготовьтесь`,
    )
  }, [mine, enabled, queueTitle])

  // Заголовок вкладки: место в очереди или мигающее «Вас вызвали!».
  useEffect(() => {
    const base = 'LabFlow'
    if (!mine) {
      document.title = base
      return
    }
    if (mine.status === 'called') {
      let on = true
      const t = setInterval(() => {
        document.title = on ? '🔔 Вас вызвали!' : base
        on = !on
      }, 1000)
      return () => {
        clearInterval(t)
        document.title = base
      }
    }
    document.title = mine.status === 'waiting' ? `№${mine.position} · ${base}` : base
    return () => {
      document.title = base
    }
  }, [mine])

  const supported = typeof window !== 'undefined' && 'Notification' in window
  const denied = supported && Notification.permission === 'denied'
  return { enabled, toggle, denied }
}
