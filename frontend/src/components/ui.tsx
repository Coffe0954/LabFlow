import type { ReactNode } from 'react'
import { errorText } from '../api/client'
import type { EntryStatus } from '../api/types'
import { STATUS_LABELS } from '../format'
import { Icon, type IconName } from './Icon'

/** Заглушка-«скелет», пока грузятся данные. */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" role="status" aria-label="Загрузка">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton-line" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  )
}

export function Spinner({ label = 'Загрузка…' }: { label?: string }) {
  return (
    <div className="card">
      <Skeleton />
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <div className="alert alert-error" role="alert">
      <Icon name="alert" size={18} />
      <span>{errorText(error)}</span>
    </div>
  )
}

export function StatusBadge({ status }: { status: EntryStatus }) {
  return (
    <span className={`badge badge-${status}`}>
      <span className="badge-dot" />
      {STATUS_LABELS[status]}
    </span>
  )
}

export function Empty({ children, icon = 'queue' }: { children: ReactNode; icon?: IconName }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name={icon} size={28} />
      </span>
      <div>{children}</div>
    </div>
  )
}

export function LiveDot({ live }: { live: boolean }) {
  return (
    <span
      className={`live ${live ? 'live-on' : ''}`}
      title={live ? 'Обновляется мгновенно' : 'Связь восстанавливается, обновление раз в 5 секунд'}
    >
      {live ? 'онлайн' : 'переподключение…'}
    </span>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
  back,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  back?: ReactNode
}) {
  return (
    <div className="page-header">
      {back}
      <div className="page-header-row">
        <div className="page-header-text">
          <h1>{title}</h1>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
        {actions && <div className="page-header-actions">{actions}</div>}
      </div>
    </div>
  )
}

export function Progress({ value, tone }: { value: number; tone?: 'ok' | 'warn' | 'bad' }) {
  const pct = Math.max(0, Math.min(100, value * 100))
  return (
    <div
      className={`progress ${tone ? `progress-${tone}` : ''}`}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="progress-bar" style={{ width: `${pct}%` }} />
    </div>
  )
}

export function StatTile({
  label,
  value,
  icon,
  tone,
}: {
  label: string
  value: ReactNode
  icon?: IconName
  tone?: 'ok' | 'bad' | 'warn' | 'accent'
}) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ''}`}>
      {icon && (
        <span className="stat-icon">
          <Icon name={icon} size={18} />
        </span>
      )}
      <b>{value}</b>
      <span className="muted">{label}</span>
    </div>
  )
}

export function Avatar({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('')
  // Стабильный цвет по имени.
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 360
  return (
    <span className="avatar" style={{ '--hue': hash } as React.CSSProperties} aria-hidden>
      {initials || '?'}
    </span>
  )
}
