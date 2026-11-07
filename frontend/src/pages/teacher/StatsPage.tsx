import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { components } from '../../api/schema'
import type { EntryStatus, QueueState, QueueStats } from '../../api/types'
import { Icon } from '../../components/Icon'
import { Empty, ErrorBox, PageHeader, Spinner, StatTile, StatusBadge } from '../../components/ui'
import { downloadFile, STATUS_LABELS, toCsv } from '../../format'

type LabTiming = components['schemas']['LabTiming']

const min = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v)} мин`)

export function StatsPage() {
  const queueId = Number(useParams().id)
  const stats = useQuery({
    queryKey: ['stats', queueId],
    queryFn: () => api<QueueStats>(`/queues/${queueId}/stats`),
    refetchInterval: 30_000,
  })
  const state = useQuery({
    queryKey: ['queue', queueId],
    queryFn: () => api<QueueState>(`/queues/${queueId}`),
  })
  if (stats.error) return <ErrorBox error={stats.error} />
  if (!stats.data) return <Spinner />
  const d = stats.data
  const title = state.data?.queue.discipline_title ?? 'Очередь'

  const exportCsv = () => {
    const rows = [
      ['ФИО', 'Группа', 'Лабы', 'Результат', 'Записался', 'Ждал, мин', 'Сдавал, мин', 'Тест, %'],
      ...d.results.map((r) => [
        r.student_name,
        r.group,
        r.labs.join(', '),
        STATUS_LABELS[r.status as EntryStatus] ?? r.status,
        new Date(r.created_at).toLocaleString('ru-RU'),
        r.wait_min != null ? Math.round(r.wait_min) : '',
        r.service_min != null ? Math.round(r.service_min) : '',
        r.score,
      ]),
    ]
    const date = state.data?.queue.date ?? ''
    downloadFile(`labflow-${title}-${date}.csv`.replace(/\s+/g, '_'), toCsv(rows))
  }

  return (
    <>
      <PageHeader
        back={
          <Link to={`/teacher/queues/${queueId}`} className="back">
            <Icon name="arrowLeft" size={16} /> К очереди
          </Link>
        }
        title="Статистика"
        subtitle={title}
        actions={
          <button className="btn btn-ghost" onClick={exportCsv} disabled={d.results.length === 0}>
            <Icon name="download" size={18} /> Скачать CSV
          </button>
        }
      />
      <div className="stats">
        <StatTile label="Сдали" value={d.passed} icon="award" tone="ok" />
        <StatTile label="Не сдали" value={d.failed} icon="x" tone="bad" />
        <StatTile label="Ждут" value={d.waiting} icon="users" />
        <StatTile label="Среднее ожидание" value={min(d.avg_wait_min)} icon="clock" />
        <StatTile label="Средняя сдача" value={min(d.avg_service_min)} icon="clock" />
        <StatTile
          label="Средний балл теста"
          value={d.avg_score == null ? '—' : `${d.avg_score}%`}
          icon="flask"
          tone="accent"
        />
      </div>

      <Outcomes stats={d} />
      <LabTimings labs={d.labs} />

      <section className="card">
        <h3>Ведомость ({d.results.length})</h3>
        {d.results.length === 0 ? (
          <Empty>Пока никто не записался</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Студент</th>
                  <th>Лабы</th>
                  <th>Итог</th>
                  <th className="num">Ждал</th>
                  <th className="num">Тест</th>
                </tr>
              </thead>
              <tbody>
                {d.results.map((r) => (
                  <tr key={r.entry_id}>
                    <td>
                      {r.student_name}
                      {r.group && <small className="muted"> · {r.group}</small>}
                    </td>
                    <td>{r.labs.join(', ')}</td>
                    <td>
                      <StatusBadge status={r.status as EntryStatus} />
                    </td>
                    <td className="num">{min(r.wait_min)}</td>
                    <td className="num">{r.score == null ? '—' : `${r.score}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}

/** Исход сдач: одна полоса, сегменты в статусных цветах + подписи и легенда. */
function Outcomes({ stats }: { stats: QueueStats }) {
  const parts = [
    { key: 'passed', label: 'Сдали', value: stats.passed },
    { key: 'failed', label: 'Не сдали', value: stats.failed },
    { key: 'left', label: 'Вышли', value: stats.left },
  ]
  const total = parts.reduce((a, p) => a + p.value, 0)
  return (
    <section className="card">
      <h3>Итоги сдач</h3>
      {total === 0 ? (
        <Empty icon="chart">Здесь появится распределение, когда кто-нибудь сдаст</Empty>
      ) : (
        <>
          <div
            className="outcome-bar"
            role="img"
            aria-label={parts.map((p) => `${p.label}: ${p.value}`).join(', ')}
          >
            {parts
              .filter((p) => p.value > 0)
              .map((p) => (
                <div
                  key={p.key}
                  className={`outcome-seg outcome-${p.key}`}
                  style={{ flexGrow: p.value }}
                  title={`${p.label}: ${p.value} (${Math.round((p.value / total) * 100)}%)`}
                >
                  {p.value / total >= 0.12 && <span>{Math.round((p.value / total) * 100)}%</span>}
                </div>
              ))}
          </div>
          <ul className="legend">
            {parts.map((p) => (
              <li key={p.key}>
                <span className={`legend-swatch outcome-${p.key}`} />
                {p.label} <b>{p.value}</b>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

/** План и факт по каждой лабе — горизонтальные столбцы на одной оси (минуты). */
function LabTimings({ labs }: { labs: LabTiming[] }) {
  const max = Math.max(1, ...labs.flatMap((l) => [l.expected_minutes, l.actual_avg_min ?? 0]))
  const advice = labs.filter(
    (l) =>
      l.actual_avg_min != null &&
      l.samples >= 3 &&
      Math.abs(l.actual_avg_min - l.expected_minutes) / l.expected_minutes > 0.25,
  )
  return (
    <section className="card">
      <div className="section-head">
        <h3>Сколько длится сдача</h3>
        <ul className="legend">
          <li>
            <span className="legend-swatch series-plan" /> План
          </li>
          <li>
            <span className="legend-swatch series-fact" /> Факт
          </li>
        </ul>
      </div>
      <p className="muted small">
        Чем точнее план, тем точнее студенты видят время ожидания. Факт считается по завершённым
        сдачам.
      </p>
      <div className="bars">
        {labs.map((l) => (
          <div key={l.lab_id} className="bars-row">
            <span className="bars-label" title={l.title}>
              ЛР {l.number}
            </span>
            <div className="bars-track">
              <div className="bar-line">
                <div
                  className="bar series-plan"
                  style={{ width: `${(l.expected_minutes / max) * 100}%` }}
                  title={`ЛР ${l.number}, план: ${l.expected_minutes} мин`}
                />
                <span className="bar-value">{l.expected_minutes} мин</span>
              </div>
              <div className="bar-line">
                {l.actual_avg_min != null ? (
                  <>
                    <div
                      className="bar series-fact"
                      style={{ width: `${(l.actual_avg_min / max) * 100}%` }}
                      title={`ЛР ${l.number}, факт: ${Math.round(l.actual_avg_min)} мин (сдач: ${l.samples})`}
                    />
                    <span className="bar-value">
                      {Math.round(l.actual_avg_min)} мин · {l.samples}
                    </span>
                  </>
                ) : (
                  <span className="bar-value muted">нет данных</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
      {advice.length > 0 && (
        <div className="alert">
          <Icon name="sliders" size={18} />
          <span>
            Совет: обновите длительность в «Лабы и тесты» —{' '}
            {advice
              .map(
                (l) =>
                  `ЛР ${l.number}: ${Math.round(l.actual_avg_min ?? 0)} мин вместо ${l.expected_minutes}`,
              )
              .join('; ')}
            .
          </span>
        </div>
      )}
    </section>
  )
}
