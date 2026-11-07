import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { Discipline, Queue } from '../../api/types'
import { Icon } from '../../components/Icon'
import { useToast } from '../../components/Toast'
import { Empty, ErrorBox, PageHeader, Skeleton } from '../../components/ui'
import { formatDate, formatTime, isoDate, plural } from '../../format'

type NewQueue = Pick<Queue, 'discipline_id' | 'date' | 'starts_at' | 'ends_at' | 'aging_k'>

export function TeacherHome() {
  const open = useQuery({
    queryKey: ['queues', 'mine', 'open'],
    queryFn: () => api<Queue[]>('/queues?mine=true&status=open'),
    refetchInterval: 20_000,
  })
  const closed = useQuery({
    queryKey: ['queues', 'mine', 'closed'],
    queryFn: () => api<Queue[]>('/queues?mine=true&status=closed'),
  })
  const today = isoDate()
  const todays = open.data?.filter((q) => q.date === today) ?? []
  const others = open.data?.filter((q) => q.date !== today) ?? []

  return (
    <>
      <PageHeader
        title="Мои очереди"
        subtitle="Создайте очередь на пару — студенты запишутся сами"
      />
      <CreateQueue />
      <ErrorBox error={open.error} />
      {open.isPending && <Skeleton lines={4} />}
      {open.data?.length === 0 && (
        <Empty icon="calendar">Открытых очередей нет — создайте новую на ближайшую пару</Empty>
      )}
      {todays.length > 0 && (
        <section className="section">
          <h2 className="section-title">Сегодня</h2>
          <div className="grid">
            {todays.map((q) => (
              <QueueCard key={q.id} q={q} />
            ))}
          </div>
        </section>
      )}
      {others.length > 0 && (
        <section className="section">
          <h2 className="section-title">Другие дни</h2>
          <div className="grid">
            {others.map((q) => (
              <QueueCard key={q.id} q={q} />
            ))}
          </div>
        </section>
      )}
      {closed.data && closed.data.length > 0 && (
        <details className="section closed">
          <summary className="section-title">Закрытые ({closed.data.length})</summary>
          <div className="grid">
            {closed.data.map((q) => (
              <QueueCard key={q.id} q={q} />
            ))}
          </div>
        </details>
      )}
    </>
  )
}

function QueueCard({ q }: { q: Queue }) {
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const repeat = useMutation({
    mutationFn: () => {
      // Та же пара через неделю.
      const [y, m, d] = q.date.split('-').map(Number)
      const body: NewQueue = {
        discipline_id: q.discipline_id,
        date: isoDate(7, new Date(y, m - 1, d)),
        starts_at: q.starts_at,
        ends_at: q.ends_at,
        aging_k: q.aging_k,
      }
      return api<Queue>('/queues', 'POST', body)
    },
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ['queues'] })
      toast(`Очередь создана на ${formatDate(created.date)}`)
      navigate(`/teacher/queues/${created.id}`)
    },
    onError: (e) => toast(e.message, 'error'),
  })
  return (
    <div className={`card queue-card ${q.status === 'closed' ? 'queue-card-closed' : ''}`}>
      <Link to={`/teacher/queues/${q.id}`} className="queue-card-link">
        <div className="queue-card-top">
          <span className="queue-card-icon">
            <Icon name="book" />
          </span>
          <span className={`chip ${q.status === 'open' ? 'chip-ok' : ''}`}>
            {q.status === 'open' ? 'запись открыта' : 'закрыта'}
          </span>
        </div>
        <h3>{q.discipline_title}</h3>
        <p className="muted small">
          <Icon name="calendar" size={14} /> {formatDate(q.date)}, {formatTime(q.starts_at)}–
          {formatTime(q.ends_at)}
        </p>
        <p>
          <b>{q.waiting_count}</b> {plural(q.waiting_count, ['ждёт', 'ждут', 'ждут'])}
        </p>
      </Link>
      <div className="queue-card-foot">
        <Link to={`/teacher/queues/${q.id}`} className="btn btn-sm btn-primary">
          Открыть
        </Link>
        <button
          className="btn btn-sm btn-ghost"
          onClick={() => repeat.mutate()}
          disabled={repeat.isPending}
          title="Создать такую же очередь на ту же пару через неделю"
        >
          <Icon name="repeat" size={16} /> Через неделю
        </button>
      </div>
    </div>
  )
}

function CreateQueue() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const toast = useToast()
  const disciplines = useQuery({
    queryKey: ['disciplines'],
    queryFn: () => api<Discipline[]>('/disciplines'),
  })
  const [form, setForm] = useState({
    discipline_id: '',
    date: isoDate(),
    starts_at: '09:00',
    ends_at: '10:30',
    aging_k: '0.5',
  })
  const create = useMutation({
    mutationFn: () =>
      api<Queue>('/queues', 'POST', {
        ...form,
        discipline_id: Number(form.discipline_id || disciplines.data?.[0]?.id),
        aging_k: Number(form.aging_k),
      }),
    onSuccess: (q) => {
      qc.invalidateQueries({ queryKey: ['queues'] })
      toast('Очередь создана — отправьте студентам ссылку')
      navigate(`/teacher/queues/${q.id}`)
    },
  })
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm({ ...form, [key]: e.target.value })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate()
  }

  if (disciplines.data?.length === 0)
    return (
      <div className="alert">
        <Icon name="alert" size={18} />
        <span>
          Сначала добавьте дисциплину и лабы в разделе{' '}
          <Link to="/teacher/tests">«Лабы и тесты»</Link>.
        </span>
      </div>
    )

  // Быстрые пресеты пар МАИ.
  const PAIRS = [
    ['09:00', '10:30'],
    ['10:45', '12:15'],
    ['13:00', '14:30'],
    ['14:45', '16:15'],
    ['16:30', '18:00'],
  ]

  return (
    <details className="card create-queue">
      <summary>
        <span className="btn btn-primary btn-sm">
          <Icon name="plus" size={16} /> Создать очередь
        </span>
      </summary>
      <form className="form-grid" onSubmit={submit}>
        <label className="span-2">
          Дисциплина
          <select value={form.discipline_id} onChange={set('discipline_id')}>
            {disciplines.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Дата
          <input type="date" required value={form.date} onChange={set('date')} />
        </label>
        <div className="span-2 pairs">
          <span className="muted small">Пара:</span>
          {PAIRS.map(([s, e], i) => (
            <button
              key={s}
              type="button"
              className={`chip chip-btn ${form.starts_at === s && form.ends_at === e ? 'chip-accent' : ''}`}
              onClick={() => setForm({ ...form, starts_at: s, ends_at: e })}
            >
              {i + 1} · {s}
            </button>
          ))}
        </div>
        <label>
          Начало
          <input type="time" required value={form.starts_at} onChange={set('starts_at')} />
        </label>
        <label>
          Конец
          <input type="time" required value={form.ends_at} onChange={set('ends_at')} />
        </label>
        <label title="Насколько быстро растёт приоритет ожидающих: key = D − k·W">
          Aging k
          <input
            type="number"
            step="0.1"
            min="0.1"
            max="10"
            required
            value={form.aging_k}
            onChange={set('aging_k')}
          />
        </label>
        <p className="hint small span-2">
          k — насколько быстро растёт приоритет тех, кто долго ждёт. При k = 0.5 студент с
          30-минутной лабой обгонит любого новичка максимум через час.
        </p>
        <ErrorBox error={create.error} />
        <button className="btn btn-primary" disabled={create.isPending}>
          Создать
        </button>
      </form>
    </details>
  )
}
