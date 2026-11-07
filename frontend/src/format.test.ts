import { describe, expect, it } from 'vitest'
import {
  clockIn,
  formatTimer,
  formatWait,
  isoDate,
  labsShort,
  minutesUntil,
  plural,
  toCsv,
} from './format'

describe('formatWait', () => {
  it('показывает «следующий» для нулевого ожидания', () => {
    expect(formatWait(0)).toBe('следующий')
  })
  it('до 10 минут — точно', () => {
    expect(formatWait(7)).toBe('≈ 7 мин')
  })
  it('дальше округляет до 5 минут', () => {
    expect(formatWait(23)).toBe('≈ 25 мин')
    expect(formatWait(61)).toBe('≈ 1 ч')
    expect(formatWait(95)).toBe('≈ 1 ч 35 мин')
  })
  it('пусто, если времени нет', () => {
    expect(formatWait(null)).toBe('')
  })
})

describe('labsShort', () => {
  it('перечисляет номера лаб', () => {
    const lab = (number: number) => ({
      id: number,
      discipline_id: 1,
      number,
      title: '',
      expected_minutes: 10,
    })
    expect(labsShort([lab(1), lab(3)])).toBe('ЛР 1, ЛР 3')
  })
})

describe('новые помощники', () => {
  it('склоняет слова по числу', () => {
    const f: [string, string, string] = ['студент', 'студента', 'студентов']
    expect([1, 2, 5, 11, 21, 22, 25, 111].map((n) => plural(n, f))).toEqual([
      'студент',
      'студента',
      'студентов',
      'студентов',
      'студент',
      'студента',
      'студентов',
      'студентов',
    ])
  })

  it('форматирует таймер', () => {
    expect(formatTimer(0)).toBe('00:00')
    expect(formatTimer(452)).toBe('07:32')
    expect(formatTimer(-5)).toBe('00:00')
  })

  it('считает минуты до конца пары и время по часам', () => {
    const now = new Date(2026, 10, 7, 10, 0)
    expect(minutesUntil('2026-11-07', '10:30', now)).toBe(30)
    expect(minutesUntil('2026-11-07', '09:30:00', now)).toBe(-30)
    expect(clockIn(45, now)).toBe('10:45')
    expect(isoDate(7, now)).toBe('2026-11-14')
    expect(isoDate(30, now)).toBe('2026-12-07')
  })

  it('собирает CSV для Excel: BOM, «;» и экранирование', () => {
    const csv = toCsv([
      ['ФИО', 'Тест'],
      ['Иванов; Иван', 100],
      ['Кто-то "в кавычках"', null],
    ])
    expect(csv.startsWith('﻿')).toBe(true)
    expect(csv.slice(1).split('\r\n')).toEqual([
      'ФИО;Тест',
      '"Иванов; Иван";100',
      '"Кто-то ""в кавычках""";',
    ])
  })
})
