import type { EntryStatus, Lab } from './api/types'

/** «≈ 25 мин»: до 10 минут — точно, дальше округляем до 5. */
export function formatWait(minutes: number | null | undefined): string {
  if (minutes == null) return ''
  if (minutes <= 0) return 'следующий'
  const rounded = minutes < 10 ? Math.ceil(minutes) : Math.round(minutes / 5) * 5
  if (rounded < 60) return `≈ ${rounded} мин`
  const h = Math.floor(rounded / 60)
  const m = rounded % 60
  return m ? `≈ ${h} ч ${m} мин` : `≈ ${h} ч`
}

/** Время по часам через N минут: «10:45». */
export function clockIn(minutes: number, now: Date = new Date()): string {
  const t = new Date(now.getTime() + minutes * 60_000)
  return t.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

/** Секунды → «07:32». */
export function formatTimer(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export const STATUS_LABELS: Record<EntryStatus, string> = {
  waiting: 'ждёт',
  called: 'вызван',
  testing: 'проходит тест',
  reviewing: 'проверка кода',
  passed: 'сдал',
  failed: 'не сдал',
  left: 'вышел',
}

export function labsShort(labs: Lab[]): string {
  return labs.map((l) => `ЛР ${l.number}`).join(', ')
}

export function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    weekday: 'short',
  })
}

export const formatTime = (t: string) => t.slice(0, 5)

/** Локальная дата «YYYY-MM-DD» со сдвигом на N дней. */
export function isoDate(shiftDays = 0, from: Date = new Date()): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate() + shiftDays)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Минут от «сейчас» до времени окончания очереди (date + ends_at), может быть < 0. */
export function minutesUntil(dateIso: string, time: string, now: Date = new Date()): number {
  const [y, m, d] = dateIso.split('-').map(Number)
  const [hh, mm] = time.split(':').map(Number)
  return (new Date(y, m - 1, d, hh, mm).getTime() - now.getTime()) / 60_000
}

/** Склонение: plural(3, ['студент', 'студента', 'студентов']). */
export function plural(n: number, forms: [string, string, string]): string {
  const a = Math.abs(n) % 100
  const b = a % 10
  if (a > 10 && a < 20) return forms[2]
  if (b > 1 && b < 5) return forms[1]
  if (b === 1) return forms[0]
  return forms[2]
}

/** CSV для Excel: разделитель «;» и BOM, чтобы кириллица открывалась без «кракозябр». */
export function toCsv(rows: (string | number | null | undefined)[][]): string {
  const cell = (v: string | number | null | undefined) => {
    const s = v == null ? '' : String(v)
    return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return '﻿' + rows.map((r) => r.map(cell).join(';')).join('\r\n')
}

export function downloadFile(name: string, content: string, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
