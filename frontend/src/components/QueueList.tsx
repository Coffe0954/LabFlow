import type { QueueState } from '../api/types'
import { formatWait, labsShort } from '../format'
import { Avatar, Empty, StatusBadge } from './ui'

/** Очередь глазами студента: сдающие сейчас и ожидающие, своё место подсвечено. */
export function QueueList({ state, myId }: { state: QueueState; myId?: number }) {
  return (
    <>
      {state.in_progress.length > 0 && (
        <section className="card">
          <h3>Сейчас сдают</h3>
          <ul className="list">
            {state.in_progress.map((e) => (
              <li key={e.id} className={e.student_id === myId ? 'row row-me' : 'row'}>
                <Avatar name={e.student_name} />
                <span className="row-main">
                  <span className="row-name">{e.student_name}</span>
                  <small className="muted">{labsShort(e.labs)}</small>
                </span>
                <StatusBadge status={e.status} />
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="card">
        <h3>Ожидают ({state.waiting.length})</h3>
        {state.waiting.length === 0 ? (
          <Empty>В очереди пока никого нет</Empty>
        ) : (
          <ol className="list">
            {state.waiting.map((e) => {
              const me = e.student_id === myId
              return (
                <li
                  key={e.id}
                  className={me ? 'row row-me' : 'row'}
                  aria-current={me ? 'true' : undefined}
                >
                  <span className="pos">{e.position}</span>
                  <span className="row-main">
                    <span className="row-name">
                      {e.student_name}
                      {me && <b className="me-tag"> (вы)</b>}
                    </span>
                    <small className="muted">
                      {labsShort(e.labs)} · ~{e.duration_min} мин
                    </small>
                  </span>
                  <span className="wait">{formatWait(e.wait_minutes)}</span>
                </li>
              )
            })}
          </ol>
        )}
      </section>
    </>
  )
}
