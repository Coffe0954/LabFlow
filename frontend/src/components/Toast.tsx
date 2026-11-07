import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { Icon } from './Icon'

type Kind = 'success' | 'error' | 'info'
interface ToastItem {
  id: number
  kind: Kind
  text: string
}

type Notify = (text: string, kind?: Kind) => void
const ToastContext = createContext<Notify>(() => {})

let nextId = 1

/** Короткие всплывающие сообщения: «Сохранено», «Ссылка скопирована» и т. п. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const remove = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), [])

  const notify = useCallback<Notify>(
    (text, kind = 'success') => {
      const id = nextId++
      setItems((all) => [...all.slice(-2), { id, kind, text }])
      setTimeout(() => remove(id), kind === 'error' ? 6000 : 3500)
    },
    [remove],
  )

  const value = useMemo(() => notify, [notify])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <Icon name={t.kind === 'error' ? 'alert' : t.kind === 'info' ? 'bell' : 'check'} />
            <span>{t.text}</span>
            <button className="toast-close" onClick={() => remove(t.id)} aria-label="Закрыть">
              <Icon name="x" size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useToast = () => useContext(ToastContext)
