import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, queueSocketUrl } from '../api/client'
import type { QueueState } from '../api/types'

const POLL_MS = 5000
const PING_MS = 25_000
const MAX_RETRY_MS = 30_000

export const queueKey = (id: number) => ['queue', id] as const

/**
 * Состояние очереди в реальном времени.
 * Основной канал — WebSocket; при разрыве переподключаемся с нарастающей паузой,
 * а пока соединения нет — опрашиваем сервер раз в 5 секунд.
 */
export function useQueueState(queueId: number) {
  const qc = useQueryClient()
  const [live, setLive] = useState(false)

  useEffect(() => {
    let ws: WebSocket | null = null
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let pingTimer: ReturnType<typeof setInterval> | undefined
    let attempt = 0
    let stopped = false

    const connect = () => {
      ws = new WebSocket(queueSocketUrl(queueId))
      ws.onopen = () => {
        attempt = 0
        setLive(true)
        pingTimer = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send('ping'), PING_MS)
      }
      ws.onmessage = (event) => {
        if (typeof event.data !== 'string' || event.data === 'pong') return
        try {
          const msg = JSON.parse(event.data) as { type: string; data: QueueState }
          if (msg.type === 'queue_state') qc.setQueryData(queueKey(queueId), msg.data)
        } catch {
          /* битое сообщение — пропускаем */
        }
      }
      ws.onclose = () => {
        setLive(false)
        clearInterval(pingTimer)
        if (stopped) return
        const delay = Math.min(MAX_RETRY_MS, 1000 * 2 ** attempt++)
        retryTimer = setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimeout(retryTimer)
      clearInterval(pingTimer)
      if (ws?.readyState === WebSocket.CONNECTING) {
        // Закрывать сокет до установки соединения нельзя без ошибки в консоли —
        // дожидаемся открытия и сразу закрываем.
        const pending = ws
        pending.onopen = () => pending.close()
        pending.onmessage = null
        pending.onclose = null
      } else if (ws) {
        ws.onclose = null // не трогаем индикатор «онлайн» — это уже чужое соединение
        ws.close()
      }
    }
  }, [queueId, qc])

  const query = useQuery({
    queryKey: queueKey(queueId),
    queryFn: () => api<QueueState>(`/queues/${queueId}`),
    refetchInterval: live ? false : POLL_MS,
  })
  return { ...query, live }
}
