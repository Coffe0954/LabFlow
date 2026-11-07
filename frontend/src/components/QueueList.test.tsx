import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Entry, QueueState } from '../api/types'
import { QueueList } from './QueueList'

const lab = { id: 1, discipline_id: 1, number: 2, title: 'Наследование', expected_minutes: 15 }

function entry(id: number, name: string, extra: Partial<Entry> = {}): Entry {
  return {
    id,
    student_id: id,
    student_name: name,
    group: null,
    status: 'waiting',
    labs: [lab],
    duration_min: 15,
    position: id,
    wait_minutes: (id - 1) * 15,
    pinned_position: null,
    created_at: '2026-11-07T09:00:00Z',
    called_at: null,
    ...extra,
  }
}

const state: QueueState = {
  queue: {
    id: 1,
    discipline_id: 1,
    discipline_title: 'ООП',
    teacher_id: 9,
    teacher_name: 'Петров',
    date: '2026-11-07',
    starts_at: '09:00:00',
    ends_at: '10:30:00',
    status: 'open',
    aging_k: 0.5,
    waiting_count: 2,
  },
  waiting: [entry(1, 'Анна'), entry(2, 'Борис')],
  in_progress: [entry(3, 'Вера', { status: 'testing', position: null, wait_minutes: null })],
  current_remaining_min: 5,
  finished_count: 0,
  updated_at: '2026-11-07T09:10:00Z',
}

describe('QueueList', () => {
  it('подсвечивает моё место и показывает время ожидания', () => {
    render(<QueueList state={state} myId={2} />)
    const mine = screen.getByText('Борис').closest('li')!
    expect(mine).toHaveClass('row-me')
    expect(mine).toHaveAttribute('aria-current', 'true')
    expect(mine).toHaveTextContent('(вы)')
    expect(mine).toHaveTextContent('≈ 15 мин')
    expect(screen.getByText('Анна').closest('li')).not.toHaveClass('row-me')
  })

  it('показывает тех, кто сдаёт сейчас, со статусом', () => {
    render(<QueueList state={state} />)
    expect(screen.getByText('Сейчас сдают')).toBeInTheDocument()
    expect(screen.getByText('проходит тест')).toBeInTheDocument()
  })

  it('пустая очередь', () => {
    render(<QueueList state={{ ...state, waiting: [], in_progress: [] }} />)
    expect(screen.getByText('В очереди пока никого нет')).toBeInTheDocument()
  })
})
