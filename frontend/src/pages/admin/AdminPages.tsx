import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import type { Ad, Role, User } from '../../api/types'
import { Empty, ErrorBox, PageHeader, Spinner } from '../../components/ui'

const ROLE_LABELS: Record<Role, string> = {
  student: 'Студент',
  teacher: 'Преподаватель',
  admin: 'Администратор',
}

export function UsersPage() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState('')
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') })
  const setRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: Role }) =>
      api<User>(`/users/${id}`, 'PATCH', { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
  const f = filter.trim().toLowerCase()
  const list = users.data?.filter(
    (u) => !f || u.full_name.toLowerCase().includes(f) || u.email.toLowerCase().includes(f),
  )
  return (
    <>
      <PageHeader
        title="Пользователи"
        subtitle="Новые пользователи — студенты. Роль меняется здесь"
      />
      <input
        className="input-wide"
        placeholder="Поиск по имени или email"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <ErrorBox error={users.error ?? setRole.error} />
      {users.isPending && <Spinner />}
      <ul className="list card">
        {list?.map((u) => (
          <li key={u.id} className="row">
            <span className="row-main">
              {u.full_name}
              <small className="muted">
                {' '}
                · {u.email}
                {u.group && ` · ${u.group}`}
              </small>
            </span>
            <select
              value={u.role}
              aria-label="Роль"
              onChange={(e) => setRole.mutate({ id: u.id, role: e.target.value as Role })}
            >
              {Object.entries(ROLE_LABELS).map(([r, label]) => (
                <option key={r} value={r}>
                  {label}
                </option>
              ))}
            </select>
          </li>
        ))}
      </ul>
    </>
  )
}

export function AdsPage() {
  const qc = useQueryClient()
  const ads = useQuery({ queryKey: ['ads'], queryFn: () => api<Ad[]>('/ads') })
  const [form, setForm] = useState({ image_url: '', link: '' })
  const done = () => {
    qc.invalidateQueries({ queryKey: ['ads'] })
    qc.invalidateQueries({ queryKey: ['ad'] })
  }
  const create = useMutation({
    mutationFn: () => api<Ad>('/ads', 'POST', { ...form, active: true }),
    onSuccess: () => {
      setForm({ image_url: '', link: '' })
      done()
    },
  })
  const toggle = useMutation({
    mutationFn: (ad: Ad) => api<Ad>(`/ads/${ad.id}`, 'PATCH', { active: !ad.active }),
    onSuccess: done,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api<void>(`/ads/${id}`, 'DELETE'),
    onSuccess: done,
  })
  return (
    <>
      <PageHeader
        title="Рекламные баннеры"
        subtitle="Активный баннер показывается под контентом и не перекрывает очередь"
      />
      <form
        className="card form-grid"
        onSubmit={(e) => {
          e.preventDefault()
          create.mutate()
        }}
      >
        <label>
          Картинка (URL)
          <input
            type="url"
            required
            value={form.image_url}
            onChange={(e) => setForm({ ...form, image_url: e.target.value })}
          />
        </label>
        <label>
          Ссылка
          <input
            type="url"
            required
            value={form.link}
            onChange={(e) => setForm({ ...form, link: e.target.value })}
          />
        </label>
        <ErrorBox error={create.error} />
        <button className="btn btn-primary">Добавить</button>
      </form>
      <ErrorBox error={toggle.error ?? remove.error} />
      {ads.isPending && <Spinner />}
      {ads.data?.length === 0 && <Empty>Баннеров нет</Empty>}
      <div className="grid">
        {ads.data?.map((ad) => (
          <div key={ad.id} className="card">
            <img className="ad-preview" src={ad.image_url} alt="" />
            <p className="small">
              <a href={ad.link} target="_blank" rel="noreferrer">
                {ad.link}
              </a>
            </p>
            <div className="inline">
              <button className="btn btn-ghost" onClick={() => toggle.mutate(ad)}>
                {ad.active ? 'Выключить' : 'Включить'}
              </button>
              <button
                className="link-btn danger"
                onClick={() => confirm('Удалить баннер?') && remove.mutate(ad.id)}
              >
                удалить
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
