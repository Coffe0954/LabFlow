import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent, type InputHTMLAttributes } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { TokenOut } from '../api/types'
import { Icon } from '../components/Icon'
import { ErrorBox } from '../components/ui'
import { useAuth } from '../hooks/useAuth'

function PasswordInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false)
  return (
    <span className="password">
      <input {...props} type={visible ? 'text' : 'password'} />
      <button
        type="button"
        className="password-toggle"
        onClick={() => setVisible(!visible)}
        aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}
        title={visible ? 'Скрыть пароль' : 'Показать пароль'}
      >
        <Icon name={visible ? 'eyeOff' : 'eye'} size={18} />
      </button>
    </span>
  )
}

function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-wrap">
      <div className="auth-hero">
        <span className="auth-hero-mark">
          <Icon name="queue" size={28} />
        </span>
        <h2>Очередь на сдачу лаб — без толпы у двери</h2>
        <ul className="auth-points">
          <li>
            <Icon name="check" size={16} /> Запись за минуту с телефона
          </li>
          <li>
            <Icon name="clock" size={16} /> Видно своё место и время ожидания
          </li>
          <li>
            <Icon name="bell" size={16} /> Уведомление, когда вас вызывают
          </li>
        </ul>
      </div>
      {children}
    </div>
  )
}

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const login = useMutation({
    mutationFn: () => api<TokenOut>('/auth/login', 'POST', { email: email.trim(), password }),
    onSuccess: (data) => {
      signIn(data)
      navigate('/')
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    login.mutate()
  }
  return (
    <AuthShell>
      <form className="card auth" onSubmit={submit}>
        <h1>Вход</h1>
        <label>
          Логин или email
          <input
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            autoFocus
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <div className="field">
          <label htmlFor="login-password">Пароль</label>
          <PasswordInput
            id="login-password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <ErrorBox error={login.error} />
        <button className="btn btn-primary btn-lg" disabled={login.isPending}>
          {login.isPending ? 'Входим…' : 'Войти'}
        </button>
        <p className="muted center">
          Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
        </p>
        {import.meta.env.DEV && (
          <p className="hint small">
            Демо: <code>student</code>, <code>teacher</code>, <code>admin</code> — пароль{' '}
            <code>1234</code>
          </p>
        )}
      </form>
    </AuthShell>
  )
}

export function RegisterPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '', full_name: '', group: '' })
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm({ ...form, [key]: e.target.value })
  const register = useMutation({
    mutationFn: () =>
      api<TokenOut>('/auth/register', 'POST', {
        ...form,
        email: form.email.trim(),
        group: form.group.trim() || null,
      }),
    onSuccess: (data) => {
      signIn(data)
      navigate('/')
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    register.mutate()
  }
  return (
    <AuthShell>
      <form className="card auth" onSubmit={submit}>
        <h1>Регистрация</h1>
        <label>
          ФИО
          <input
            required
            minLength={2}
            autoComplete="name"
            placeholder="Иванов Иван"
            value={form.full_name}
            onChange={set('full_name')}
          />
        </label>
        <label>
          Группа
          <input placeholder="М8О-312БВ-24" value={form.group} onChange={set('group')} />
        </label>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={set('email')}
          />
        </label>
        <div className="field">
          <label htmlFor="register-password">Пароль (от 6 символов)</label>
          <PasswordInput
            id="register-password"
            autoComplete="new-password"
            required
            minLength={6}
            maxLength={72}
            value={form.password}
            onChange={set('password')}
          />
        </div>
        <ErrorBox error={register.error} />
        <button className="btn btn-primary btn-lg" disabled={register.isPending}>
          {register.isPending ? 'Создаём аккаунт…' : 'Зарегистрироваться'}
        </button>
        <p className="muted center">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </p>
      </form>
    </AuthShell>
  )
}
