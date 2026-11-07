import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, tokenStore } from '../api/client'
import type { TokenOut, User } from '../api/types'

interface AuthValue {
  user: User | null
  loading: boolean
  signIn: (data: TokenOut) => void
  signOut: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

const meKey = (token: string | null) => ['me', token] as const

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  // Токен — состояние React: при входе/выходе всё приложение сразу перерисовывается.
  const [token, setToken] = useState<string | null>(() => tokenStore.get())

  const me = useQuery({
    queryKey: meKey(token),
    queryFn: () => api<User>('/auth/me'),
    enabled: token !== null,
    retry: false,
    staleTime: 5 * 60_000,
  })

  const signIn = useCallback(
    (data: TokenOut) => {
      tokenStore.set(data.access_token)
      qc.removeQueries() // данные прошлого пользователя не должны протечь
      qc.setQueryData(meKey(data.access_token), data.user)
      setToken(data.access_token)
    },
    [qc],
  )

  const signOut = useCallback(() => {
    tokenStore.clear()
    setToken(null)
    qc.removeQueries()
  }, [qc])

  // Сервер ответил 401 — токен истёк или неверный, выходим.
  useEffect(() => {
    const onUnauthorized = () => {
      if (tokenStore.get() !== null || token !== null) signOut()
    }
    window.addEventListener('labflow:unauthorized', onUnauthorized)
    return () => window.removeEventListener('labflow:unauthorized', onUnauthorized)
  }, [signOut, token])

  const value = useMemo<AuthValue>(
    () => ({
      user: token !== null ? (me.data ?? null) : null,
      loading: token !== null && me.isPending,
      signIn,
      signOut,
    }),
    [token, me.data, me.isPending, signIn, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth вне AuthProvider')
  return ctx
}
