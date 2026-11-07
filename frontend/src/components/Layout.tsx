import { NavLink, Outlet } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from '../hooks/useAuth'
import { useOnline } from '../hooks/useNow'
import { useTheme, type ThemeMode } from '../hooks/useTheme'
import { AdBanner } from './AdBanner'
import { Icon, type IconName } from './Icon'
import { Avatar } from './ui'

const NAV: Record<Role, { to: string; label: string; icon: IconName; end?: boolean }[]> = {
  student: [
    { to: '/queues', label: 'Очереди', icon: 'queue' },
    { to: '/results', label: 'Результаты', icon: 'award' },
  ],
  teacher: [
    { to: '/teacher', label: 'Очереди', icon: 'queue', end: true },
    { to: '/teacher/tests', label: 'Лабы и тесты', icon: 'flask' },
  ],
  admin: [
    { to: '/admin/users', label: 'Пользователи', icon: 'users' },
    { to: '/admin/ads', label: 'Баннеры', icon: 'image' },
  ],
}

const ROLE_LABEL: Record<Role, string> = {
  student: 'студент',
  teacher: 'преподаватель',
  admin: 'администратор',
}

const THEME: Record<ThemeMode, { icon: IconName; label: string }> = {
  auto: { icon: 'auto', label: 'Тема: как в системе' },
  light: { icon: 'sun', label: 'Тема: светлая' },
  dark: { icon: 'moon', label: 'Тема: тёмная' },
}

export function Layout() {
  const { user, signOut } = useAuth()
  const { mode, cycle } = useTheme()
  const online = useOnline()
  const nav = user ? NAV[user.role] : []

  return (
    <div className={`app ${user ? 'app-with-tabs' : ''}`}>
      <header className="header">
        <div className="header-inner">
          <NavLink to="/" className="logo" aria-label="LabFlow — на главную">
            <span>
              Lab<b>Flow</b>
            </span>
          </NavLink>

          {user && (
            <nav className="nav-desktop" aria-label="Основное меню">
              {nav.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end}>
                  <Icon name={item.icon} size={18} />
                  {item.label}
                </NavLink>
              ))}
            </nav>
          )}

          <div className="header-tools">
            <button
              className="icon-btn"
              onClick={cycle}
              title={THEME[mode].label}
              aria-label={THEME[mode].label}
            >
              <Icon name={THEME[mode].icon} />
            </button>
            {user && (
              <>
                <span className="user-chip" title={user.email}>
                  <Avatar name={user.full_name} />
                  <span className="user-chip-text">
                    <b>{user.full_name}</b>
                    <small>{ROLE_LABEL[user.role]}</small>
                  </span>
                </span>
                <button className="icon-btn" onClick={signOut} title="Выйти" aria-label="Выйти">
                  <Icon name="logout" />
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {!online && (
        <div className="offline" role="alert">
          <Icon name="wifiOff" size={16} /> Нет интернета — данные обновятся, когда связь вернётся
        </div>
      )}

      <main className="main">
        <Outlet />
      </main>

      <footer className="footer">
        <AdBanner />
        <p className="muted small">LabFlow · умная очередь на сдачу лаб · М8О-312БВ-24</p>
      </footer>

      {user && (
        <nav className="tabbar" aria-label="Меню">
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              <Icon name={item.icon} size={22} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  )
}
