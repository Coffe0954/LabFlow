import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { EntryStatus, MyStats } from '../../api/types'
import { Empty, ErrorBox, PageHeader, Spinner, StatTile, StatusBadge } from '../../components/ui'
import { formatDate } from '../../format'

export function ResultsPage() {
  const { data, error, isPending } = useQuery({
    queryKey: ['stats', 'me'],
    queryFn: () => api<MyStats>('/stats/me'),
  })
  if (error) return <ErrorBox error={error} />
  if (isPending) return <Spinner />
  return (
    <>
      <PageHeader title="Мои результаты" subtitle="Все ваши сдачи и тесты" />
      <div className="stats">
        <StatTile label="Сдано работ" value={data.passed_count} icon="award" tone="ok" />
        <StatTile label="Пройдено тестов" value={data.attempts_count} icon="flask" />
        <StatTile
          label="Средний балл"
          value={data.avg_score != null ? `${data.avg_score}%` : '—'}
          icon="chart"
          tone="accent"
        />
        <StatTile
          label="Среднее ожидание"
          value={data.avg_wait_min != null ? `${Math.round(data.avg_wait_min)} мин` : '—'}
          icon="clock"
        />
      </div>
      {data.entries.length === 0 ? (
        <Empty icon="award">
          Вы ещё не записывались в очереди. <Link to="/queues">Найти очередь</Link>
        </Empty>
      ) : (
        <section className="card">
          <h3>История</h3>
          <ul className="list">
            {data.entries.map((e) => (
              <li key={e.entry_id} className="row">
                <span className="row-main">
                  <Link to={`/queues/${e.queue_id}`} className="row-name">
                    {e.discipline_title}
                  </Link>
                  <small className="muted">
                    {formatDate(e.date)} · {e.labs.join(', ')}
                    {e.score != null && ` · тест ${e.score}%`}
                  </small>
                </span>
                <StatusBadge status={e.status as EntryStatus} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
