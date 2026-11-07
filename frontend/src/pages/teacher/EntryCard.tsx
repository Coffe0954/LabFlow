import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import type { Attempt, AttemptReview, Entry, EntryDetail, EntryStatus } from '../../api/types'
import { ErrorBox, Spinner, StatusBadge } from '../../components/ui'

/** Карточка студента: лабы, запуск теста, результат, «Сдал / не сдал». */
export function EntryCard({ entryId, onClose }: { entryId: number; onClose: () => void }) {
  const qc = useQueryClient()
  const key = ['entry', entryId]
  const entry = useQuery({
    queryKey: key,
    queryFn: () => api<EntryDetail>(`/entries/${entryId}`),
    // Пока студент проходит тест — обновляем, чтобы увидеть результат.
    refetchInterval: (q) => (q.state.data?.status === 'testing' ? 3000 : false),
  })
  const [testId, setTestId] = useState<number | ''>('')

  const refresh = () => {
    qc.invalidateQueries({ queryKey: key })
  }
  const setStatus = useMutation({
    mutationFn: (status: EntryStatus) =>
      api<Entry>(`/entries/${entryId}/status`, 'PATCH', { status }),
    onSuccess: (e) => {
      refresh()
      if (['passed', 'failed', 'left', 'waiting'].includes(e.status)) onClose()
    },
  })
  const startTest = useMutation({
    mutationFn: () =>
      api<Attempt>(`/entries/${entryId}/test/start`, 'POST', { test_id: testId || null }),
    onSuccess: refresh,
  })

  const e = entry.data
  return (
    <div className="drawer-bg" onClick={onClose}>
      <aside
        className="drawer"
        onClick={(ev) => ev.stopPropagation()}
        aria-label="Карточка студента"
      >
        <button className="drawer-close" onClick={onClose} aria-label="Закрыть">
          ×
        </button>
        {entry.error && <ErrorBox error={entry.error} />}
        {!e ? (
          <Spinner />
        ) : (
          <>
            <h2>{e.student_name}</h2>
            <p className="muted">
              {e.group ?? 'группа не указана'} · <StatusBadge status={e.status} />
            </p>
            <h3>Лабы</h3>
            <ul>
              {e.labs.map((l) => (
                <li key={l.id}>
                  ЛР {l.number}. {l.title}{' '}
                  <small className="muted">~{l.expected_minutes} мин</small>
                </li>
              ))}
            </ul>

            {(e.status === 'called' || e.status === 'reviewing') && (
              <div className="box">
                <h3>Тест</h3>
                {e.available_tests.length === 0 ? (
                  <p className="muted">Для этих лаб тестов нет.</p>
                ) : (
                  <div className="inline">
                    <select
                      value={testId}
                      onChange={(ev) => setTestId(ev.target.value ? Number(ev.target.value) : '')}
                    >
                      <option value="">{e.available_tests[0].title}</option>
                      {e.available_tests.slice(1).map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.title}
                        </option>
                      ))}
                    </select>
                    <button
                      className="btn btn-primary"
                      disabled={startTest.isPending}
                      onClick={() => startTest.mutate()}
                    >
                      Запустить тест
                    </button>
                  </div>
                )}
                <ErrorBox error={startTest.error} />
              </div>
            )}
            {e.status === 'testing' && <p className="alert">Студент проходит тест…</p>}

            {e.attempts.map((a) => (
              <AttemptBlock key={a.id} attempt={a} />
            ))}

            <ErrorBox error={setStatus.error} />
            <div className="actions">
              {e.status === 'waiting' && (
                <button className="btn btn-primary" onClick={() => setStatus.mutate('called')}>
                  Вызвать
                </button>
              )}
              {['called', 'testing', 'reviewing'].includes(e.status) && (
                <>
                  <button className="btn btn-success" onClick={() => setStatus.mutate('passed')}>
                    Сдал
                  </button>
                  <button className="btn btn-danger" onClick={() => setStatus.mutate('failed')}>
                    Не сдал
                  </button>
                </>
              )}
              {e.status === 'called' && (
                <button className="btn btn-ghost" onClick={() => setStatus.mutate('waiting')}>
                  Вернуть в очередь
                </button>
              )}
              {['waiting', 'called', 'testing', 'reviewing'].includes(e.status) && (
                <button
                  className="btn btn-ghost"
                  onClick={() => confirm('Убрать студента из очереди?') && setStatus.mutate('left')}
                >
                  Убрать
                </button>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

function AttemptBlock({ attempt }: { attempt: AttemptReview }) {
  const show = (value: unknown, options: string[]) => {
    if (value == null || value === '') return '—'
    if (Array.isArray(value)) return value.map((v) => options[Number(v)] ?? v).join(', ')
    if (typeof value === 'number') return options[value] ?? String(value)
    return String(value)
  }
  return (
    <div className="box">
      <h3>
        {attempt.test_title}:{' '}
        {attempt.finished_at ? <b>{attempt.score}%</b> : <span className="muted">идёт</span>}
      </h3>
      {attempt.finished_at && (
        <ol className="review">
          {attempt.review.map((r) => (
            <li key={r.question_id} className={r.is_correct ? 'ok' : 'bad'}>
              {r.text}
              <br />
              <small>
                Ответ: {show(r.value, r.options)}
                {!r.is_correct && <> · верно: {show(r.correct, r.options)}</>}
              </small>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
