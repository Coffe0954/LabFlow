import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { Attempt, AttemptFull, EntryDetail } from '../../api/types'
import { Icon } from '../../components/Icon'
import { Empty, ErrorBox, Progress, Spinner } from '../../components/ui'
import { formatTimer } from '../../format'
import { useNow } from '../../hooks/useNow'

type Answers = Record<number, unknown>
type Question = AttemptFull['questions'][number]

function isAnswered(value: unknown): boolean {
  if (value == null) return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'string') return value.trim() !== ''
  return true
}

export function TestPage() {
  const current = useQuery({
    queryKey: ['attempt', 'current'],
    queryFn: () => api<AttemptFull | null>('/attempts/current'),
    refetchOnWindowFocus: false,
  })
  const [result, setResult] = useState<Attempt | null>(null)

  if (result) return <TestResult attempt={result} />
  if (current.error) return <ErrorBox error={current.error} />
  if (current.isPending) return <Spinner />
  if (!current.data)
    return (
      <Empty icon="flask">
        Активного теста нет. Его запускает преподаватель, когда вызывает вас.
        <br />
        <Link to="/queues">К очередям</Link>
      </Empty>
    )
  return <TestForm attempt={current.data} onDone={setResult} />
}

function TestForm({ attempt, onDone }: { attempt: AttemptFull; onDone: (a: Attempt) => void }) {
  const [answers, setAnswers] = useState<Answers>(attempt.answers as Answers)
  const now = useNow(1000)
  const total = attempt.time_limit_min * 60
  const left = Math.max(
    0,
    Math.floor((new Date(attempt.deadline).getTime() - now.getTime()) / 1000),
  )
  const finishedRef = useRef(false)

  const save = useMutation({
    mutationFn: (payload: Answers) =>
      api<AttemptFull>(`/attempts/${attempt.id}/answers`, 'POST', {
        answers: Object.entries(payload).map(([question_id, value]) => ({
          question_id: Number(question_id),
          value,
        })),
      }),
  })
  const finish = useMutation({
    mutationFn: async () => {
      try {
        await save.mutateAsync(answers)
      } catch {
        /* время могло выйти — сервер всё равно завершит попытку с сохранёнными ответами */
      }
      return api<Attempt>(`/attempts/${attempt.id}/finish`, 'POST')
    },
    onSuccess: onDone,
  })

  // Автоотправка, когда время вышло.
  useEffect(() => {
    if (left === 0 && !finishedRef.current) {
      finishedRef.current = true
      finish.mutate()
    }
  }, [left, finish])

  const setAnswer = (q: Question, value: unknown) => {
    setAnswers({ ...answers, [q.id]: value })
    if (q.kind !== 'text') save.mutate({ [q.id]: value }) // текст сохраняем при уходе с поля
  }

  const answered = attempt.questions.filter((q) => isAnswered(answers[q.id])).length
  const missing = attempt.questions.length - answered

  const submit = () => {
    const warn = missing > 0 ? `Без ответа: ${missing}. ` : ''
    if (confirm(`${warn}Отправить ответы? Изменить их будет нельзя.`)) finish.mutate()
  }

  return (
    <>
      <div className="test-bar">
        <div className="test-bar-row">
          <h1>{attempt.test_title}</h1>
          <span className={`timer ${left < 60 ? 'timer-low' : ''}`} aria-label="Осталось времени">
            <Icon name="clock" size={18} /> {formatTimer(left)}
          </span>
        </div>
        <Progress
          value={left / total}
          tone={left < 60 ? 'bad' : left < total / 3 ? 'warn' : 'ok'}
        />
        <p className="muted small">
          Отвечено {answered} из {attempt.questions.length}
          {save.isPending && ' · сохраняем…'}
          {save.isError && ' · не удалось сохранить, ответы отправятся при завершении'}
        </p>
      </div>

      {attempt.questions.map((q, i) => (
        <section
          key={q.id}
          className={`card question-card ${isAnswered(answers[q.id]) ? 'answered' : ''}`}
        >
          <p className="question">
            <span className="question-num">{i + 1}</span>
            <span>{q.text}</span>
          </p>
          {q.kind === 'multi' && <p className="muted small">Можно выбрать несколько вариантов</p>}
          {q.kind === 'single' &&
            q.options.map((opt, idx) => (
              <label key={idx} className={answers[q.id] === idx ? 'check check-on' : 'check'}>
                <input
                  type="radio"
                  name={`q${q.id}`}
                  checked={answers[q.id] === idx}
                  onChange={() => setAnswer(q, idx)}
                />
                <span>{opt}</span>
              </label>
            ))}
          {q.kind === 'multi' &&
            q.options.map((opt, idx) => {
              const value = (answers[q.id] as number[] | undefined) ?? []
              const on = value.includes(idx)
              return (
                <label key={idx} className={on ? 'check check-on' : 'check'}>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() =>
                      setAnswer(q, on ? value.filter((v) => v !== idx) : [...value, idx])
                    }
                  />
                  <span>{opt}</span>
                </label>
              )
            })}
          {q.kind === 'text' && (
            <input
              className="input-wide"
              placeholder="Ваш ответ"
              value={(answers[q.id] as string | undefined) ?? ''}
              onChange={(e) => setAnswer(q, e.target.value)}
              onBlur={(e) => save.mutate({ [q.id]: e.target.value })}
            />
          )}
        </section>
      ))}
      <ErrorBox error={finish.error} />
      <button
        className="btn btn-primary btn-lg btn-block"
        disabled={finish.isPending}
        onClick={submit}
      >
        {finish.isPending ? 'Отправляем…' : 'Отправить ответы'}
      </button>
    </>
  )
}

function TestResult({ attempt }: { attempt: Attempt }) {
  const entry = useQuery({
    queryKey: ['entry', attempt.entry_id],
    queryFn: () => api<EntryDetail>(`/entries/${attempt.entry_id}`),
  })
  const score = attempt.score ?? 0
  return (
    <section className="card hero result-card">
      <div
        className={`score-ring ${score >= 60 ? 'score-good' : 'score-low'}`}
        style={{ '--p': score } as React.CSSProperties}
      >
        <b>{score}%</b>
      </div>
      <h2>Тест отправлен</h2>
      <p>Преподаватель смотрит ваш код и зафиксирует результат.</p>
      {entry.data && (
        <Link className="btn btn-primary" to={`/queues/${entry.data.queue_id}`}>
          Вернуться к очереди
        </Link>
      )}
    </section>
  )
}
