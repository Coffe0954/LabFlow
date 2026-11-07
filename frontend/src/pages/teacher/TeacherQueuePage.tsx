import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Fragment, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Entry, EntryStatus, Queue, QueueState } from '../../api/types'
import { Icon } from '../../components/Icon'
import { useToast } from '../../components/Toast'
import {
  Avatar,
  Empty,
  ErrorBox,
  LiveDot,
  PageHeader,
  Progress,
  Spinner,
  StatusBadge,
} from '../../components/ui'
import {
  formatDate,
  formatTime,
  formatTimer,
  formatWait,
  labsShort,
  minutesUntil,
  plural,
} from '../../format'
import { useNow } from '../../hooks/useNow'
import { queueKey, useQueueState } from '../../hooks/useQueueState'
import { EntryCard } from './EntryCard'

export function TeacherQueuePage() {
  const queueId = Number(useParams().id)
  const qc = useQueryClient()
  const toast = useToast()
  const { data, error, live } = useQueueState(queueId)
  const [openEntry, setOpenEntry] = useState<number | null>(null)
  const now = useNow(1000)

  const callNext = useMutation({
    mutationFn: () => api<Entry>(`/queues/${queueId}/call-next`, 'POST'),
    onSuccess: (entry) => {
      toast(`Вызван: ${entry.student_name}`)
      setOpenEntry(entry.id)
    },
    onError: (e) => toast(e.message, 'error'),
  })
  const updateQueue = useMutation({
    mutationFn: (body: Partial<Pick<Queue, 'status' | 'aging_k'>>) =>
      api<Queue>(`/queues/${queueId}`, 'PATCH', body),
    onSuccess: (q) => {
      qc.invalidateQueries({ queryKey: queueKey(queueId) })
      qc.invalidateQueries({ queryKey: ['queues'] })
      toast(q.status === 'closed' ? 'Запись закрыта' : 'Настройки сохранены')
    },
    onError: (e) => toast(e.message, 'error'),
  })

  // Горячие клавиши: N — вызвать следующего, Esc — закрыть карточку.
  const canCall = (data?.waiting.length ?? 0) > 0 && !callNext.isPending
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || e.ctrlKey || e.metaKey) return
      if (e.key === 'Escape') setOpenEntry(null)
      if (
        (e.key === 'n' || e.key === 'т' || e.key === 'N' || e.key === 'Т') &&
        openEntry === null &&
        canCall
      ) {
        e.preventDefault()
        callNext.mutate()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [canCall, callNext, openEntry])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Spinner />
  const q = data.queue
  const joinUrl = `${window.location.origin}/queues/${q.id}/join`
  const minutesLeft = minutesUntil(q.date, q.ends_at, now)

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(joinUrl)
      toast('Ссылка для записи скопирована')
    } catch {
      prompt('Скопируйте ссылку для студентов:', joinUrl)
    }
  }

  return (
    <>
      <PageHeader
        back={
          <Link to="/teacher" className="back">
            <Icon name="arrowLeft" size={16} /> Мои очереди
          </Link>
        }
        title={q.discipline_title}
        subtitle={`${formatDate(q.date)}, ${formatTime(q.starts_at)}–${formatTime(q.ends_at)}`}
        actions={<LiveDot live={live} />}
      />

      <div className="toolbar">
        <button
          className="btn btn-primary btn-lg"
          disabled={!canCall}
          onClick={() => callNext.mutate()}
          title="Горячая клавиша: N"
        >
          <Icon name="bell" size={18} /> Вызвать следующего
          <kbd>N</kbd>
        </button>
        <button className="btn btn-ghost" onClick={copyLink} title={joinUrl}>
          <Icon name="copy" size={18} /> Ссылка для записи
        </button>
        <Link
          className="btn btn-ghost"
          to={`/board/${q.id}`}
          target="_blank"
          title="Открыть на проекторе"
        >
          <Icon name="tv" size={18} /> Проектор
        </Link>
        <Link className="btn btn-ghost" to={`/teacher/queues/${queueId}/stats`}>
          <Icon name="chart" size={18} /> Статистика
        </Link>
        <button
          className="btn btn-ghost"
          title="Коэффициент aging: больше — быстрее растёт приоритет ждущих"
          onClick={() => {
            const value = prompt(
              'Коэффициент aging k (0.1–10). Больше — быстрее растёт приоритет тех, кто долго ждёт.',
              String(q.aging_k),
            )
            if (value === null) return
            const k = Number(value.replace(',', '.'))
            if (k > 0 && k <= 10) updateQueue.mutate({ aging_k: k })
            else toast('k должен быть числом от 0.1 до 10', 'error')
          }}
        >
          <Icon name="sliders" size={18} /> k = {q.aging_k}
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => updateQueue.mutate({ status: q.status === 'open' ? 'closed' : 'open' })}
        >
          {q.status === 'open' ? 'Закрыть запись' : 'Открыть запись'}
        </button>
      </div>

      <InProgress state={data} now={now} onOpen={setOpenEntry} />
      <WaitingList state={data} minutesLeft={minutesLeft} onOpen={setOpenEntry} />

      <p className="muted small center keys-hint">
        <Icon name="keyboard" size={14} /> <kbd>N</kbd> — вызвать следующего · <kbd>Esc</kbd> —
        закрыть карточку · перетаскивайте студентов за <Icon name="grip" size={14} />
      </p>

      {openEntry !== null && <EntryCard entryId={openEntry} onClose={() => setOpenEntry(null)} />}
    </>
  )
}

/** Кто сдаёт сейчас: таймер сдачи и быстрые кнопки результата. */
function InProgress({
  state,
  now,
  onOpen,
}: {
  state: QueueState
  now: Date
  onOpen: (id: number) => void
}) {
  const toast = useToast()
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: EntryStatus }) =>
      api<Entry>(`/entries/${id}/status`, 'PATCH', { status }),
    onSuccess: (e) =>
      toast(`${e.student_name}: ${e.status === 'passed' ? 'сдал ✓' : 'не сдал'}`, 'info'),
    onError: (e) => toast(e.message, 'error'),
  })

  return (
    <section className="card">
      <h3>Сдают сейчас</h3>
      {state.in_progress.length === 0 ? (
        <Empty icon="user">Никого не вызвали. Нажмите «Вызвать следующего»</Empty>
      ) : (
        <ul className="list">
          {state.in_progress.map((e) => {
            const elapsed = e.called_at
              ? (now.getTime() - new Date(e.called_at).getTime()) / 1000
              : 0
            const limit = e.duration_min * 60
            const over = elapsed > limit
            return (
              <li key={e.id} className="current">
                <div className="current-top">
                  <Avatar name={e.student_name} />
                  <button className="row-main link-btn" onClick={() => onOpen(e.id)}>
                    <span className="row-name">{e.student_name}</span>
                    <small className="muted">
                      {labsShort(e.labs)} · план {e.duration_min} мин
                    </small>
                  </button>
                  <StatusBadge status={e.status} />
                </div>
                <div className="current-timer">
                  <Progress
                    value={limit ? elapsed / limit : 0}
                    tone={over ? 'bad' : elapsed > limit * 0.8 ? 'warn' : 'ok'}
                  />
                  <span className={over ? 'text-bad' : 'muted'}>
                    <Icon name="clock" size={14} /> {formatTimer(elapsed)}
                    {over && ' · дольше плана'}
                  </span>
                </div>
                <div className="current-actions">
                  <button
                    className="btn btn-sm btn-success"
                    disabled={setStatus.isPending}
                    onClick={() => setStatus.mutate({ id: e.id, status: 'passed' })}
                  >
                    <Icon name="check" size={16} /> Сдал
                  </button>
                  <button
                    className="btn btn-sm btn-danger"
                    disabled={setStatus.isPending}
                    onClick={() => setStatus.mutate({ id: e.id, status: 'failed' })}
                  >
                    <Icon name="x" size={16} /> Не сдал
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => onOpen(e.id)}>
                    Карточка / тест
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function WaitingList({
  state,
  minutesLeft,
  onOpen,
}: {
  state: QueueState
  minutesLeft: number
  onOpen: (id: number) => void
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const key = queueKey(state.queue.id)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  const pin = useMutation({
    mutationFn: ({ id, position }: { id: number; position: number | null }) =>
      api<Entry>(`/entries/${id}/position`, 'PATCH', { position }),
    onSuccess: (e, vars) =>
      toast(
        vars.position
          ? `${e.student_name} закреплён на ${vars.position}-м месте`
          : `${e.student_name}: закрепление снято`,
        'info',
      ),
    onError: (e) => toast(e.message, 'error'),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  })

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const from = state.waiting.findIndex((e) => e.id === active.id)
    const to = state.waiting.findIndex((e) => e.id === over.id)
    // Оптимистично двигаем у себя, сервер пришлёт точный порядок.
    qc.setQueryData<QueueState>(key, (old) =>
      old ? { ...old, waiting: arrayMove(old.waiting, from, to) } : old,
    )
    pin.mutate({ id: Number(active.id), position: to + 1 })
  }

  // Прогноз: кто не успеет до конца пары.
  const late = (e: Entry) => minutesLeft > 0 && (e.wait_minutes ?? 0) + e.duration_min > minutesLeft
  const firstLate = state.waiting.findIndex(late)
  const lateCount = firstLate === -1 ? 0 : state.waiting.length - firstLate
  const totalMin =
    state.current_remaining_min + state.waiting.reduce((a, e) => a + e.duration_min, 0)

  return (
    <section className="card">
      <div className="section-head">
        <h3>Ожидают ({state.waiting.length})</h3>
        {state.waiting.length > 0 && (
          <span className="muted small">всего ≈ {formatWait(totalMin).replace('≈ ', '')}</span>
        )}
      </div>
      {lateCount > 0 && (
        <div className="alert alert-warn">
          <Icon name="alert" size={18} />
          <span>
            До конца пары {Math.round(minutesLeft)} мин — {lateCount}{' '}
            {plural(lateCount, ['студент', 'студента', 'студентов'])} скорее всего{' '}
            {lateCount === 1 ? 'не успеет' : 'не успеют'}.
          </span>
        </div>
      )}
      <ErrorBox error={pin.error} />
      {state.waiting.length === 0 ? (
        <Empty>Очередь пуста. Отправьте студентам ссылку для записи</Empty>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext
            items={state.waiting.map((e) => e.id)}
            strategy={verticalListSortingStrategy}
          >
            <ol className="list">
              {state.waiting.map((e, i) => (
                <Fragment key={e.id}>
                  {i === firstLate && (
                    <li className="divider" aria-hidden>
                      <span>не успевают до {formatTime(state.queue.ends_at)}</span>
                    </li>
                  )}
                  <SortableRow
                    entry={e}
                    late={firstLate !== -1 && i >= firstLate}
                    onOpen={() => onOpen(e.id)}
                    onUnpin={() => pin.mutate({ id: e.id, position: null })}
                  />
                </Fragment>
              ))}
            </ol>
          </SortableContext>
        </DndContext>
      )}
    </section>
  )
}

function SortableRow({
  entry,
  late,
  onOpen,
  onUnpin,
}: {
  entry: Entry
  late: boolean
  onOpen: () => void
  onUnpin: () => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: entry.id,
  })
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={`row row-drag ${isDragging ? 'row-dragging' : ''} ${late ? 'row-late' : ''}`}
    >
      <span className="handle" {...attributes} {...listeners} aria-label="Перетащить">
        <Icon name="grip" size={18} />
      </span>
      <span className="pos">{entry.position}</span>
      <button className="row-main link-btn" onClick={onOpen}>
        <span className="row-name">{entry.student_name}</span>
        <small className="muted">
          {labsShort(entry.labs)} · {entry.duration_min} мин
        </small>
      </button>
      {entry.pinned_position != null && (
        <button
          className="pin"
          title="Снять закрепление"
          aria-label="Снять закрепление"
          onClick={onUnpin}
        >
          <Icon name="pin" size={16} />
        </button>
      )}
      <span className="wait">{formatWait(entry.wait_minutes)}</span>
    </li>
  )
}
