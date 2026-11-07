import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Entry, Lab, QueueState } from '../../api/types'
import { Icon } from '../../components/Icon'
import { useToast } from '../../components/Toast'
import { ErrorBox, PageHeader, Spinner } from '../../components/ui'
import { formatWait } from '../../format'
import { useAuth } from '../../hooks/useAuth'
import { queueKey } from '../../hooks/useQueueState'
import { storage } from '../../storage'

const lastLabsKey = (disciplineId: number) => `labflow_labs_${disciplineId}`

/** Выбор лаб и запись (клики 2 и 3 из 3). */
export function JoinPage() {
  const queueId = Number(useParams().id)
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()
  const [picked, setPicked] = useState<Set<number> | null>(null)

  const state = useQuery({
    queryKey: queueKey(queueId),
    queryFn: () => api<QueueState>(`/queues/${queueId}`),
  })
  const disciplineId = state.data?.queue.discipline_id
  const labs = useQuery({
    queryKey: ['labs', disciplineId],
    queryFn: () => api<Lab[]>(`/labs?discipline_id=${disciplineId}`),
    enabled: disciplineId !== undefined,
  })

  const join = useMutation({
    mutationFn: (labIds: number[]) =>
      api<Entry>(`/queues/${queueId}/entries`, 'POST', { lab_ids: labIds }),
    onSuccess: (entry, labIds) => {
      if (disciplineId !== undefined) storage.setJSON(lastLabsKey(disciplineId), labIds)
      qc.invalidateQueries({ queryKey: queueKey(queueId) })
      qc.invalidateQueries({ queryKey: ['entries', 'me'] })
      toast(entry.position ? `Вы записаны! Ваше место — ${entry.position}` : 'Вы записаны!')
      navigate(`/queues/${queueId}`)
    },
  })

  if (state.error) return <ErrorBox error={state.error} />
  if (!state.data || !labs.data) return <Spinner />

  const s = state.data
  const alreadyIn = [...s.waiting, ...s.in_progress].some((e) => e.student_id === user?.id)
  if (alreadyIn) return <Navigate to={`/queues/${queueId}`} replace />

  // По умолчанию: единственная лаба или те, что выбирали в прошлый раз (если ещё есть).
  const ids = new Set(labs.data.map((l) => l.id))
  const remembered = storage
    .getJSON<number[]>(lastLabsKey(s.queue.discipline_id), [])
    .filter((id) => ids.has(id))
  const selected = picked ?? new Set(labs.data.length === 1 ? [labs.data[0].id] : remembered)
  const toggle = (id: number) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setPicked(next)
  }
  const total = labs.data
    .filter((l) => selected.has(l.id))
    .reduce((a, l) => a + l.expected_minutes, 0)
  // Верхняя оценка ожидания: все, кто уже стоит, плюс текущий сдающий.
  const maxWait = s.current_remaining_min + s.waiting.reduce((a, e) => a + e.duration_min, 0)

  return (
    <>
      <PageHeader
        back={
          <Link to="/queues" className="back">
            <Icon name="arrowLeft" size={16} /> Все очереди
          </Link>
        }
        title={s.queue.discipline_title}
        subtitle={`${s.queue.teacher_name} · в очереди ${s.waiting.length}`}
      />
      {s.queue.status === 'closed' ? (
        <div className="alert">
          <Icon name="alert" size={18} /> Запись в эту очередь закрыта
        </div>
      ) : (
        <section className="card">
          <h3>Какие лабы сдаёте?</h3>
          <p className="muted small">
            Короткие сдачи идут быстрее, но долго ждущие тоже не застрянут — приоритет растёт со
            временем.
          </p>
          <div className="checks">
            {labs.data.map((lab) => (
              <label key={lab.id} className={selected.has(lab.id) ? 'check check-on' : 'check'}>
                <input
                  type="checkbox"
                  checked={selected.has(lab.id)}
                  onChange={() => toggle(lab.id)}
                />
                <span className="check-text">
                  <b>
                    ЛР {lab.number}. {lab.title}
                  </b>
                  <small className="muted">~{lab.expected_minutes} мин</small>
                </span>
              </label>
            ))}
          </div>
          <div className="join-summary">
            <span>
              <Icon name="clock" size={16} /> {total ? `Сдача ~${total} мин` : 'Отметьте лабы'}
            </span>
            <span>
              <Icon name="users" size={16} />{' '}
              {maxWait <= 0
                ? 'Очереди нет — вы будете первым'
                : `Ожидание до ${formatWait(maxWait).replace('≈ ', '')}`}
            </span>
          </div>
          <ErrorBox error={join.error} />
          <button
            className="btn btn-primary btn-lg btn-block"
            disabled={selected.size === 0 || join.isPending}
            onClick={() => join.mutate([...selected])}
          >
            {selected.size === 0 ? 'Отметьте хотя бы одну лабу' : 'Записаться'}
          </button>
        </section>
      )}
    </>
  )
}
