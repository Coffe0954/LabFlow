import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import type { TokenOut } from '../api/types'
import { AuthProvider, useAuth } from './useAuth'

const session = (name: string, role: TokenOut['user']['role']): TokenOut => ({
  access_token: `token-${name}`,
  token_type: 'bearer',
  user: { id: 1, email: name, full_name: name, group: null, role },
})

function Probe() {
  const { user, signIn, signOut } = useAuth()
  return (
    <>
      <p>{user ? `${user.full_name}:${user.role}` : 'гость'}</p>
      <button onClick={() => signIn(session('student', 'student'))}>войти студентом</button>
      <button onClick={() => signIn(session('teacher', 'teacher'))}>войти преподавателем</button>
      <button onClick={signOut}>выйти</button>
    </>
  )
}

const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }))

function renderAuth() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('useAuth', () => {
  beforeEach(() => localStorage.clear())

  // Регрессия: после «Войти» пользователь оставался на странице входа.
  it('сразу после входа пользователь считается вошедшим', () => {
    renderAuth()
    expect(screen.getByText('гость')).toBeInTheDocument()
    click('войти студентом')
    expect(screen.getByText('student:student')).toBeInTheDocument()
    expect(localStorage.getItem('labflow_token')).toBe('token-student')
  })

  it('выход и вход другим пользователем не оставляет старых данных', () => {
    renderAuth()
    click('войти студентом')
    click('выйти')
    expect(screen.getByText('гость')).toBeInTheDocument()
    expect(localStorage.getItem('labflow_token')).toBeNull()
    click('войти преподавателем')
    expect(screen.getByText('teacher:teacher')).toBeInTheDocument()
  })
})
