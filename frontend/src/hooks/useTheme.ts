import { useCallback, useEffect, useState } from 'react'
import { storage } from '../storage'

export type ThemeMode = 'auto' | 'light' | 'dark'
const KEY = 'labflow_theme'
const ORDER: ThemeMode[] = ['auto', 'light', 'dark']

function apply(mode: ThemeMode) {
  const root = document.documentElement
  if (mode === 'auto') delete root.dataset.theme
  else root.dataset.theme = mode
}

/** Тема: как в системе / светлая / тёмная. Выбор запоминается в браузере. */
export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const saved = storage.get(KEY)
    return saved === 'light' || saved === 'dark' ? saved : 'auto'
  })
  useEffect(() => {
    apply(mode)
    storage.set(KEY, mode)
  }, [mode])
  const cycle = useCallback(() => setMode((m) => ORDER[(ORDER.indexOf(m) + 1) % ORDER.length]), [])
  return { mode, cycle }
}
