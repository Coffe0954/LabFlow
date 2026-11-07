import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import type {
  Discipline,
  Lab,
  QuestionIn,
  QuestionKind,
  QuestionOut,
  TestDetail,
  TestOut,
} from '../../api/types'
import { Empty, ErrorBox, PageHeader, Spinner } from '../../components/ui'

/** Дисциплины → лабы (с длительностью) → тесты → вопросы. */
export function TestsPage() {
  const qc = useQueryClient()
  const disciplines = useQuery({
    queryKey: ['disciplines'],
    queryFn: () => api<Discipline[]>('/disciplines'),
  })
  const [picked, setPicked] = useState<number | null>(null)
  const disciplineId = picked ?? disciplines.data?.[0]?.id ?? null
  const [title, setTitle] = useState('')
  const addDiscipline = useMutation({
    mutationFn: () => api<Discipline>('/disciplines', 'POST', { title }),
    onSuccess: (d) => {
      setTitle('')
      setPicked(d.id)
      qc.invalidateQueries({ queryKey: ['disciplines'] })
    },
  })

  return (
    <>
      <PageHeader
        title="Лабы и тесты"
        subtitle="Длительность лаб влияет на прогноз ожидания у студентов"
      />
      <section className="card">
        <div className="inline">
          <select
            value={disciplineId ?? ''}
            onChange={(e) => setPicked(Number(e.target.value))}
            aria-label="Дисциплина"
          >
            {disciplines.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </select>
        </div>
        <form
          className="inline"
          onSubmit={(e) => {
            e.preventDefault()
            addDiscipline.mutate()
          }}
        >
          <input
            placeholder="Новая дисциплина"
            value={title}
            required
            onChange={(e) => setTitle(e.target.value)}
          />
          <button className="btn btn-ghost">Добавить</button>
        </form>
        <ErrorBox error={addDiscipline.error} />
      </section>
      {disciplines.isPending && <Spinner />}
      {disciplineId !== null && <LabsSection disciplineId={disciplineId} />}
    </>
  )
}

function LabsSection({ disciplineId }: { disciplineId: number }) {
  const qc = useQueryClient()
  const key = ['labs', disciplineId]
  const labs = useQuery({
    queryKey: key,
    queryFn: () => api<Lab[]>(`/labs?discipline_id=${disciplineId}`),
  })
  const [form, setForm] = useState({ number: '', title: '', expected_minutes: '15' })
  const add = useMutation({
    mutationFn: () =>
      api<Lab>('/labs', 'POST', {
        discipline_id: disciplineId,
        number: Number(form.number || (labs.data?.length ?? 0) + 1),
        title: form.title,
        expected_minutes: Number(form.expected_minutes),
      }),
    onSuccess: () => {
      setForm({ number: '', title: '', expected_minutes: form.expected_minutes })
      qc.invalidateQueries({ queryKey: key })
    },
  })
  const update = useMutation({
    mutationFn: ({ id, minutes }: { id: number; minutes: number }) =>
      api<Lab>(`/labs/${id}`, 'PATCH', { expected_minutes: minutes }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api<void>(`/labs/${id}`, 'DELETE'),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  })

  return (
    <>
      {labs.data?.length === 0 && <Empty>Лаб пока нет</Empty>}
      {labs.data?.map((lab) => (
        <section key={lab.id} className="card">
          <div className="title-row">
            <h3>
              ЛР {lab.number}. {lab.title}
            </h3>
            <span className="inline">
              <label className="small">
                минут:{' '}
                <input
                  className="input-num"
                  type="number"
                  min={1}
                  max={240}
                  defaultValue={lab.expected_minutes}
                  onBlur={(e) => {
                    const minutes = Number(e.target.value)
                    if (minutes > 0 && minutes !== lab.expected_minutes)
                      update.mutate({ id: lab.id, minutes })
                  }}
                />
              </label>
              <button
                className="link-btn danger"
                onClick={() => confirm(`Удалить ЛР ${lab.number}?`) && remove.mutate(lab.id)}
              >
                удалить
              </button>
            </span>
          </div>
          <TestsForLab lab={lab} />
        </section>
      ))}
      <ErrorBox error={update.error ?? remove.error} />
      <form
        className="card form-grid"
        onSubmit={(e) => {
          e.preventDefault()
          add.mutate()
        }}
      >
        <h3>Новая лаба</h3>
        <label>
          Номер
          <input
            type="number"
            min={1}
            placeholder={String((labs.data?.length ?? 0) + 1)}
            value={form.number}
            onChange={(e) => setForm({ ...form, number: e.target.value })}
          />
        </label>
        <label>
          Название
          <input
            required
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </label>
        <label>
          Длительность сдачи, мин
          <input
            type="number"
            min={1}
            max={240}
            required
            value={form.expected_minutes}
            onChange={(e) => setForm({ ...form, expected_minutes: e.target.value })}
          />
        </label>
        <ErrorBox error={add.error} />
        <button className="btn btn-primary">Добавить лабу</button>
      </form>
    </>
  )
}

function TestsForLab({ lab }: { lab: Lab }) {
  const qc = useQueryClient()
  const key = ['tests', lab.id]
  const tests = useQuery({
    queryKey: key,
    queryFn: () => api<TestOut[]>(`/tests?lab_id=${lab.id}`),
  })
  const [openId, setOpenId] = useState<number | null>(null)
  const create = useMutation({
    mutationFn: () =>
      api<TestDetail>('/tests', 'POST', {
        lab_id: lab.id,
        title: `Тест по ЛР ${lab.number}`,
        time_limit_min: 10,
      }),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: key })
      setOpenId(t.id)
    },
  })
  return (
    <div>
      {tests.data?.map((t) => (
        <div key={t.id}>
          <button className="link-btn" onClick={() => setOpenId(openId === t.id ? null : t.id)}>
            {openId === t.id ? '▾' : '▸'} {t.title} · {t.question_count} вопр. · {t.time_limit_min}{' '}
            мин
          </button>
          {openId === t.id && (
            <TestEditor testId={t.id} onChanged={() => qc.invalidateQueries({ queryKey: key })} />
          )}
        </div>
      ))}
      <button className="link-btn" onClick={() => create.mutate()} disabled={create.isPending}>
        + тест
      </button>
      <ErrorBox error={create.error} />
    </div>
  )
}

function TestEditor({ testId, onChanged }: { testId: number; onChanged: () => void }) {
  const qc = useQueryClient()
  const key = ['test', testId]
  const test = useQuery({ queryKey: key, queryFn: () => api<TestDetail>(`/tests/${testId}`) })
  const done = () => {
    qc.invalidateQueries({ queryKey: key })
    onChanged()
  }
  const update = useMutation({
    mutationFn: (body: { title?: string; time_limit_min?: number }) =>
      api<TestDetail>(`/tests/${testId}`, 'PATCH', body),
    onSuccess: done,
  })
  const remove = useMutation({
    mutationFn: () => api<void>(`/tests/${testId}`, 'DELETE'),
    onSuccess: onChanged,
  })
  const removeQuestion = useMutation({
    mutationFn: (id: number) => api<void>(`/tests/${testId}/questions/${id}`, 'DELETE'),
    onSuccess: done,
  })

  if (!test.data) return <Spinner />
  const t = test.data
  return (
    <div className="box">
      <div className="form-grid">
        <label>
          Название
          <input
            defaultValue={t.title}
            onBlur={(e) => e.target.value !== t.title && update.mutate({ title: e.target.value })}
          />
        </label>
        <label>
          Лимит, мин
          <input
            type="number"
            min={1}
            max={180}
            defaultValue={t.time_limit_min}
            onBlur={(e) => update.mutate({ time_limit_min: Number(e.target.value) })}
          />
        </label>
      </div>
      <ol className="review">
        {t.questions.map((q) => (
          <QuestionView key={q.id} q={q} onDelete={() => removeQuestion.mutate(q.id)} />
        ))}
      </ol>
      <QuestionForm testId={testId} onSaved={done} />
      <ErrorBox error={update.error ?? removeQuestion.error ?? remove.error} />
      <button
        className="link-btn danger"
        onClick={() => confirm('Удалить тест целиком?') && remove.mutate()}
      >
        удалить тест
      </button>
    </div>
  )
}

function QuestionView({ q, onDelete }: { q: QuestionOut; onDelete: () => void }) {
  const correct = Array.isArray(q.correct) ? q.correct : [q.correct]
  return (
    <li>
      {q.text}{' '}
      <button className="link-btn danger small" onClick={onDelete}>
        удалить
      </button>
      <br />
      <small className="muted">
        {q.kind === 'text'
          ? `ответ: ${correct.join(' / ')}`
          : q.options.map((o, i) => (correct.includes(i) ? `✔ ${o}` : o)).join(' · ')}
      </small>
    </li>
  )
}

const KIND_LABELS: Record<QuestionKind, string> = {
  single: 'Один вариант',
  multi: 'Несколько вариантов',
  text: 'Текстовый ответ',
}

function QuestionForm({ testId, onSaved }: { testId: number; onSaved: () => void }) {
  const [kind, setKind] = useState<QuestionKind>('single')
  const [text, setText] = useState('')
  const [options, setOptions] = useState(['', ''])
  const [correct, setCorrect] = useState<number[]>([0])
  const [textAnswers, setTextAnswers] = useState('')

  const save = useMutation({
    mutationFn: (body: QuestionIn) => api<QuestionOut>(`/tests/${testId}/questions`, 'POST', body),
    onSuccess: () => {
      setText('')
      setOptions(['', ''])
      setCorrect([0])
      setTextAnswers('')
      onSaved()
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (kind === 'text') {
      save.mutate({
        text,
        kind,
        options: [],
        correct: textAnswers
          .split(';')
          .map((s) => s.trim())
          .filter(Boolean),
      })
    } else {
      save.mutate({ text, kind, options, correct: kind === 'single' ? correct[0] : correct })
    }
  }
  const toggleCorrect = (i: number) => {
    if (kind === 'single') setCorrect([i])
    else setCorrect(correct.includes(i) ? correct.filter((c) => c !== i) : [...correct, i])
  }

  return (
    <form className="question-form" onSubmit={submit}>
      <h4>Новый вопрос</h4>
      <select value={kind} onChange={(e) => setKind(e.target.value as QuestionKind)}>
        {Object.entries(KIND_LABELS).map(([k, label]) => (
          <option key={k} value={k}>
            {label}
          </option>
        ))}
      </select>
      <textarea
        required
        placeholder="Текст вопроса"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {kind === 'text' ? (
        <input
          required
          placeholder="Правильные ответы через ;"
          value={textAnswers}
          onChange={(e) => setTextAnswers(e.target.value)}
        />
      ) : (
        <>
          {options.map((opt, i) => (
            <div key={i} className="inline">
              <input
                type={kind === 'single' ? 'radio' : 'checkbox'}
                checked={correct.includes(i)}
                onChange={() => toggleCorrect(i)}
                aria-label="Правильный"
              />
              <input
                required
                placeholder={`Вариант ${i + 1}`}
                value={opt}
                onChange={(e) => setOptions(options.map((o, j) => (j === i ? e.target.value : o)))}
              />
              {options.length > 2 && (
                <button
                  type="button"
                  className="link-btn danger"
                  onClick={() => {
                    setOptions(options.filter((_, j) => j !== i))
                    setCorrect(correct.filter((c) => c !== i).map((c) => (c > i ? c - 1 : c)))
                  }}
                >
                  ×
                </button>
              )}
            </div>
          ))}
          <button type="button" className="link-btn" onClick={() => setOptions([...options, ''])}>
            + вариант
          </button>
        </>
      )}
      <ErrorBox error={save.error} />
      <button className="btn btn-primary" disabled={save.isPending}>
        Сохранить вопрос
      </button>
    </form>
  )
}
