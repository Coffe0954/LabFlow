import { useParams } from 'react-router-dom'
import { Icon } from '../components/Icon'
import { ErrorBox, LiveDot, Skeleton, StatusBadge } from '../components/ui'
import { formatTime, formatWait, labsShort } from '../format'
import { useNow } from '../hooks/useNow'
import { useQueueState } from '../hooks/useQueueState'

const SHOW = 12

/** Режим проектора: крупная очередь для экрана в аудитории. Обновляется сама. */
export function BoardPage() {
  const queueId = Number(useParams().id)
  const { data, error, live } = useQueueState(queueId)
  const now = useNow(1000)

  if (error) return <ErrorBox error={error} />
  if (!data) return <Skeleton lines={6} />

  const joinUrl = `${window.location.host}/queues/${queueId}/join`
  const rest = data.waiting.length - SHOW

  return (
    <div className="board">
      <header className="board-head">
        <div>
          <h1>{data.queue.discipline_title}</h1>
          <p>
            {data.queue.teacher_name} · до {formatTime(data.queue.ends_at)}
          </p>
        </div>
        <div className="board-clock">
          {now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
          <LiveDot live={live} />
        </div>
      </header>

      <div className="board-grid">
        <section className="board-now">
          <h2>Сдают</h2>
          {data.in_progress.length === 0 && <p className="board-empty">—</p>}
          {data.in_progress.map((e) => (
            <div key={e.id} className="board-current">
              <b>{e.student_name}</b>
              <StatusBadge status={e.status} />
            </div>
          ))}
          <div className="board-join">
            <Icon name="queue" size={22} />
            <div>
              Записаться: <b>{joinUrl}</b>
              <br />
              <span>
                {data.queue.status === 'open' ? 'запись открыта' : 'запись закрыта'} · проверено:{' '}
                {data.finished_count}
              </span>
            </div>
          </div>
        </section>

        <section className="board-list">
          <h2>Очередь · {data.waiting.length}</h2>
          {data.waiting.length === 0 && <p className="board-empty">Очередь пуста</p>}
          <ol>
            {data.waiting.slice(0, SHOW).map((e) => (
              <li key={e.id} className={e.position === 1 ? 'board-next' : ''}>
                <span className="board-pos">{e.position}</span>
                <span className="board-name">
                  {e.student_name}
                  <small>{labsShort(e.labs)}</small>
                </span>
                <span className="board-wait">{formatWait(e.wait_minutes)}</span>
              </li>
            ))}
          </ol>
          {rest > 0 && <p className="board-more">и ещё {rest}</p>}
        </section>
      </div>
    </div>
  )
}
