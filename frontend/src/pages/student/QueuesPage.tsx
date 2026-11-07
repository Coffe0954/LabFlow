import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { components } from '../../api/schema'
import type { Queue } from '../../api/types'
import { Icon } from '../../components/Icon'
import { Empty, ErrorBox, PageHeader, Skeleton, StatusBadge } from '../../components/ui'
import { formatDate, formatTime, formatWait, plural } from '../../format'
import { useAuth } from '../../hooks/useAuth'

type MyActive = components['schemas']['MyActiveEntry']

/** Список очередей. Клик по очереди — сразу к выбору лаб (клик 1 из 3). */
export function QueuesPage() {
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const queues = useQuery({
    queryKey: ['queues', 'open'],
    queryFn: () => api<Queue[]>('/queues'),
    refetchInterval: 15_000,
  })
  const mine = useQuery({
    queryKey: ['entries', 'me'],
    queryFn: () => api<MyActive[]>('/entries/me'),
    refetchInterval: 15_000,
  })
  const inQueue = new Set(mine.data?.map((m) => m.queue.id))
  const q = search.trim().toLowerCase()
  const list = queues.data?.filter(
    (x) =>
      !q ||
      x.discipline_title.toLowerCase().includes(q) ||
      x.teacher_name.toLowerCase().includes(q),
  )
  const firstName = user?.full_name.split(/\s+/)[1] ?? user?.full_name.split(/\s+/)[0]

  return (
    <>
      <PageHeader
        title={firstName ? `Привет, ${firstName}!` : 'Очереди'}
        subtitle="Выберите очередь, отметьте лабы — и ждите уведомления"
      />

      {mine.data && mine.data.length > 0 && (
        <section className="section">
          <h2 className="section-title">Вы в очереди</h2>
          <div className="grid">
            {mine.data.map(({ entry, queue }) => (
              <Link key={entry.id} to={`/queues/${queue.id}`} className="card card-link my-card">
                <div className="my-card-pos">
                  {entry.status === 'waiting' ? (
                    <>
                      <b>{entry.position}</b>
                      <small>место</small>
                    </>
                  ) : (
                    <Icon name="bell" size={26} />
                  )}
                </div>
                <div className="my-card-body">
                  <h3>{queue.discipline_title}</h3>
                  {entry.status === 'waiting' ? (
                    <p className="muted">Ожидание {formatWait(entry.wait_minutes)}</p>
                  ) : (
                    <StatusBadge status={entry.status} />
                  )}
                </div>
                <Icon name="arrowRight" className="muted" />
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="section">
        <div className="section-head">
          <h2 className="section-title">Открытые очереди</h2>
          {(queues.data?.length ?? 0) > 3 && (
            <label className="search">
              <Icon name="search" size={18} />
              <input
                placeholder="Дисциплина или преподаватель"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Поиск очереди"
              />
            </label>
          )}
        </div>
        <ErrorBox error={queues.error} />
        {queues.isPending && <Skeleton lines={4} />}
        {list?.length === 0 && (
          <Empty icon="calendar">
            {q ? 'Ничего не нашлось' : 'Сейчас нет открытых очередей. Загляните позже!'}
          </Empty>
        )}
        <div className="grid">
          {list?.map((queue) => {
            const joined = inQueue.has(queue.id)
            return (
              <Link
                key={queue.id}
                to={joined ? `/queues/${queue.id}` : `/queues/${queue.id}/join`}
                className="card card-link queue-card"
              >
                <div className="queue-card-top">
                  <span className="queue-card-icon">
                    <Icon name="book" />
                  </span>
                  {joined && <span className="chip chip-accent">вы записаны</span>}
                </div>
                <h3>{queue.discipline_title}</h3>
                <p className="muted small">
                  <Icon name="user" size={14} /> {queue.teacher_name}
                </p>
                <p className="muted small">
                  <Icon name="calendar" size={14} /> {formatDate(queue.date)},{' '}
                  {formatTime(queue.starts_at)}–{formatTime(queue.ends_at)}
                </p>
                <div className="queue-card-foot">
                  <span>
                    <b>{queue.waiting_count}</b>{' '}
                    {plural(queue.waiting_count, ['человек', 'человека', 'человек'])} в очереди
                  </span>
                  <span className={`btn btn-sm ${joined ? 'btn-ghost' : 'btn-primary'}`}>
                    {joined ? 'Открыть' : 'Записаться'}
                  </span>
                </div>
              </Link>
            )
          })}
        </div>
      </section>
    </>
  )
}
