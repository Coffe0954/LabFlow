import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { CSSProperties } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Entry, EntryStatus, MyStats } from '../../api/types'
import { Icon } from '../../components/Icon'
import { QueueList } from '../../components/QueueList'
import { useToast } from '../../components/Toast'
import { ErrorBox, LiveDot, PageHeader, Progress, Spinner, StatusBadge } from '../../components/ui'
import { clockIn, formatWait, labsShort } from '../../format'
import { useAuth } from '../../hooks/useAuth'
import { useCallAlert } from '../../hooks/useCallAlert'
import { useNow } from '../../hooks/useNow'
import { useQueueState } from '../../hooks/useQueueState'
import { storage } from '../../storage'

/** Прогресс ожидания: от самого большого ожидания, которое мы видели для записи, до нуля. */
function waitProgress(entry: Entry | undefined): number {
  if (!entry || entry.status !== 'waiting' || entry.wait_minutes == null) return 0
  const key = `labflow_wait0_${entry.id}`
  const initial = Math.max(Number(storage.get(key)) || 0, entry.wait_minutes)
  storage.set(key, String(initial))
  return initial > 0 ? 1 - entry.wait_minutes / initial : 1
}

export function MyQueuePage() {
  const queueId = Number(useParams().id)
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()
  const { data, error, live, refetch } = useQueueState(queueId)
  const now = useNow(30_000)

  const mine = data
    ? [...data.waiting, ...data.in_progress].find((e) => e.student_id === user?.id)
    : undefined
  const alerts = useCallAlert(mine, data?.queue.discipline_title ?? '')

  const leave = useMutation({
    mutationFn: (entryId: number) => api<void>(`/entries/${entryId}`, 'DELETE'),
    onSuccess: () => {
      toast('Вы вышли из очереди', 'info')
      qc.invalidateQueries({ queryKey: ['entries', 'me'] })
      qc.invalidateQueries({ queryKey: ['stats', 'me'] })
      refetch()
    },
  })

  if (error) return <ErrorBox error={error} />
  if (!data) return <Spinner />

  return (
    <>
      <PageHeader
        back={
          <Link to="/queues" className="back">
            <Icon name="arrowLeft" size={16} /> Все очереди
          </Link>
        }
        title={data.queue.discipline_title}
        subtitle={data.queue.teacher_name}
        actions={<LiveDot live={live} />}
      />

      {mine ? (
        <>
          {mine.status === 'waiting' && (
            <section className="card hero">
              <div className="hero-main">
                <div className="hero-pos">
                  <span className="muted">Ваше место</span>
                  <b>{mine.position}</b>
                  <span className="muted small">из {data.waiting.length}</span>
                </div>
                <div className="hero-wait">
                  <span className="muted">Ожидание</span>
                  <b>{formatWait(mine.wait_minutes)}</b>
                  {mine.wait_minutes != null && mine.wait_minutes > 0 && (
                    <span className="muted small">около {clockIn(mine.wait_minutes, now)}</span>
                  )}
                </div>
              </div>
              <Progress value={waitProgress(mine)} />
              <p className="muted small">
                {mine.position === 1
                  ? 'Вы следующий — будьте рядом с аудиторией!'
                  : `Сдаёте: ${labsShort(mine.labs)} · ~${mine.duration_min} мин`}
              </p>
              <div className="hero-actions">
                <button
                  className={`btn ${alerts.enabled ? 'btn-soft' : 'btn-ghost'}`}
                  onClick={alerts.toggle}
                  title="Звук, вибрация и уведомление, когда подойдёт очередь"
                >
                  <Icon name={alerts.enabled ? 'bell' : 'bellOff'} size={18} />
                  {alerts.enabled ? 'Уведомления включены' : 'Включить уведомления'}
                </button>
                <button
                  className="btn btn-ghost"
                  disabled={leave.isPending}
                  onClick={() => confirm('Выйти из очереди?') && leave.mutate(mine.id)}
                >
                  Выйти из очереди
                </button>
              </div>
              {alerts.enabled && alerts.denied && (
                <p className="hint small">
                  Браузер запретил уведомления — сработают звук и вибрация, пока вкладка открыта.
                </p>
              )}
            </section>
          )}

          {mine.status === 'called' && (
            <section className="card hero hero-called">
              <span className="hero-icon">
                <Icon name="bell" size={32} />
              </span>
              <h2>Вас вызвали!</h2>
              <p>Подходите к преподавателю с ноутбуком и кодом.</p>
            </section>
          )}

          {mine.status === 'testing' && (
            <section className="card hero hero-testing">
              <h2>Пора пройти тест</h2>
              <p>Преподаватель запустил тест — пока вы отвечаете, он смотрит ваш код.</p>
              <Link to="/test" className="btn btn-primary btn-lg">
                <Icon name="play" size={18} /> Пройти тест
              </Link>
            </section>
          )}

          {mine.status === 'reviewing' && (
            <section className="card hero">
              <StatusBadge status="reviewing" />
              <p>Тест отправлен, преподаватель проверяет код. Результат появится здесь.</p>
            </section>
          )}
          <ErrorBox error={leave.error} />
        </>
      ) : (
        <NotInQueue
          queueId={queueId}
          canJoin={data.queue.status === 'open'}
          onJoin={() => navigate(`/queues/${queueId}/join`)}
        />
      )}

      <QueueList state={data} myId={user?.id} />
    </>
  )
}

/** Студент не в активной очереди: показываем итог последней записи. */
function NotInQueue({
  queueId,
  canJoin,
  onJoin,
}: {
  queueId: number
  canJoin: boolean
  onJoin: () => void
}) {
  const stats = useQuery({ queryKey: ['stats', 'me'], queryFn: () => api<MyStats>('/stats/me') })
  const last = stats.data?.entries.find((e) => e.queue_id === queueId)
  const status = last?.status as EntryStatus | undefined

  if (status === 'passed') {
    return (
      <section className="card hero hero-passed">
        <Confetti />
        <span className="hero-icon">
          <Icon name="award" size={32} />
        </span>
        <h2 className="result-ok">Работа сдана ✓</h2>
        {last?.score != null && <p>Результат теста: {last.score}%</p>}
        <p className="muted small">{last?.labs.join(', ')}</p>
        {canJoin && (
          <button className="btn btn-ghost" onClick={onJoin}>
            Записаться снова
          </button>
        )}
      </section>
    )
  }
  return (
    <section className="card hero">
      {status === 'failed' && <h2 className="result-bad">Работа не сдана</h2>}
      {last && <StatusBadge status={status ?? 'left'} />}
      {last?.score != null && <p>Результат теста: {last.score}%</p>}
      {status === 'failed' && (
        <p className="muted small">Исправьте замечания и запишитесь снова — время ещё есть.</p>
      )}
      {!last && <p>Вы не в этой очереди.</p>}
      {canJoin && (
        <button className="btn btn-primary" onClick={onJoin}>
          {last ? 'Записаться снова' : 'Записаться'}
        </button>
      )}
    </section>
  )
}

function Confetti() {
  return (
    <div className="confetti" aria-hidden>
      {Array.from({ length: 18 }, (_, i) => (
        <i key={i} style={{ '--i': i } as CSSProperties} />
      ))}
    </div>
  )
}
