import type { ReactNode } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import type { Role } from './api/types'
import { Icon } from './components/Icon'
import { Layout } from './components/Layout'
import { Empty, Spinner } from './components/ui'
import { useAuth } from './hooks/useAuth'
import { AdsPage, UsersPage } from './pages/admin/AdminPages'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import { BoardPage } from './pages/BoardPage'
import { JoinPage } from './pages/student/JoinPage'
import { MyQueuePage } from './pages/student/MyQueuePage'
import { QueuesPage } from './pages/student/QueuesPage'
import { ResultsPage } from './pages/student/ResultsPage'
import { TestPage } from './pages/student/TestPage'
import { StatsPage } from './pages/teacher/StatsPage'
import { TeacherHome } from './pages/teacher/TeacherHome'
import { TeacherQueuePage } from './pages/teacher/TeacherQueuePage'
import { TestsPage } from './pages/teacher/TestsPage'

const HOME: Record<Role, string> = {
  student: '/queues',
  teacher: '/teacher',
  admin: '/admin/users',
}

/** Пускает только пользователей с нужной ролью (сервер всё равно проверяет права сам). */
function Guard({ role, children }: { role?: Role; children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  if (!user) return <Navigate to="/login" replace />
  if (role && user.role !== role) return <Navigate to={HOME[user.role]} replace />
  return children
}

function Home() {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  return <Navigate to={user ? HOME[user.role] : '/login'} replace />
}

function NotFound() {
  return (
    <Empty icon="search">
      Такой страницы нет.
      <br />
      <Link to="/">
        <Icon name="arrowLeft" size={14} /> На главную
      </Link>
    </Empty>
  )
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return user ? <Navigate to={HOME[user.role]} replace /> : children
}

export function App() {
  return (
    <Routes>
      {/* Режим проектора — на весь экран, без меню. */}
      <Route
        path="board/:id"
        element={
          <Guard>
            <BoardPage />
          </Guard>
        }
      />
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route
          path="login"
          element={
            <GuestOnly>
              <LoginPage />
            </GuestOnly>
          }
        />
        <Route
          path="register"
          element={
            <GuestOnly>
              <RegisterPage />
            </GuestOnly>
          }
        />

        <Route
          path="queues"
          element={
            <Guard role="student">
              <QueuesPage />
            </Guard>
          }
        />
        <Route
          path="queues/:id/join"
          element={
            <Guard role="student">
              <JoinPage />
            </Guard>
          }
        />
        <Route
          path="queues/:id"
          element={
            <Guard role="student">
              <MyQueuePage />
            </Guard>
          }
        />
        <Route
          path="test"
          element={
            <Guard role="student">
              <TestPage />
            </Guard>
          }
        />
        <Route
          path="results"
          element={
            <Guard role="student">
              <ResultsPage />
            </Guard>
          }
        />

        <Route
          path="teacher"
          element={
            <Guard role="teacher">
              <TeacherHome />
            </Guard>
          }
        />
        <Route
          path="teacher/queues/:id"
          element={
            <Guard role="teacher">
              <TeacherQueuePage />
            </Guard>
          }
        />
        <Route
          path="teacher/queues/:id/stats"
          element={
            <Guard role="teacher">
              <StatsPage />
            </Guard>
          }
        />
        <Route
          path="teacher/tests"
          element={
            <Guard role="teacher">
              <TestsPage />
            </Guard>
          }
        />

        <Route
          path="admin/users"
          element={
            <Guard role="admin">
              <UsersPage />
            </Guard>
          }
        />
        <Route
          path="admin/ads"
          element={
            <Guard role="admin">
              <AdsPage />
            </Guard>
          }
        />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
