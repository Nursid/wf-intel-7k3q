import { describe, expect, it } from 'vitest'
import type { MetaResponse } from '../types/api'
import {
  addDays,
  defaultFilters,
  filtersFromSearch,
  filtersToSearch,
  londonWallToUtcIso,
  periodBoundsUtc,
  rangePresets,
  toAnalysisParams,
  validateFilters,
} from './filters'
import { formatDuration, formatLocal, formatSignedMW } from './format'

const meta = {
  available_start_date: '2026-01-01',
  available_end_date: '2026-01-31',
  default_cutoff: { mode: 'relative', day_offset: 1, local_time: '09:00' },
} as unknown as MetaResponse
const defaults = defaultFilters(meta)

describe('Europe/London conversion', () => {
  it('treats January wall time as GMT', () => {
    expect(londonWallToUtcIso('2026-01-01T09:00')).toBe('2026-01-01T09:00:00Z')
  })
  it('subtracts an hour in BST', () => {
    expect(londonWallToUtcIso('2026-06-01T09:00')).toBe('2026-06-01T08:00:00Z')
  })
  it('handles the spring-forward day (23-hour day)', () => {
    const [lo, hi] = periodBoundsUtc({ ...defaults, start: '2026-03-29', end: '2026-03-29' })
    expect((hi - lo) / 3_600_000).toBe(23)
  })
  it('handles the autumn day (25-hour day)', () => {
    const [lo, hi] = periodBoundsUtc({ ...defaults, start: '2026-10-25', end: '2026-10-25' })
    expect((hi - lo) / 3_600_000).toBe(25)
  })
  it('labels local times with GMT/BST', () => {
    expect(formatLocal('2026-01-12T09:14:00Z')).toContain('GMT')
    expect(formatLocal('2026-06-12T09:14:00Z')).toContain('BST')
  })
})

describe('filters <-> URL', () => {
  it('round-trips non-default values and keeps defaults out of the URL', () => {
    const f = { ...defaults, start: '2026-01-10', offset: 0, time: '07:30' }
    const sp = filtersToSearch(f, defaults)
    expect(sp.toString()).toBe('from=2026-01-10&offset=0&time=07%3A30')
    expect(filtersFromSearch(sp, defaults)).toEqual(f)
    expect(filtersToSearch(defaults, defaults).toString()).toBe('')
  })
  it('ignores malformed values', () => {
    const f = filtersFromSearch(new URLSearchParams('from=garbage&offset=99&time=25:00'), defaults)
    expect(f).toEqual(defaults)
  })
  it('builds absolute-mode API params in UTC', () => {
    const p = toAnalysisParams({ ...defaults, mode: 'absolute', decision: '2025-12-31T09:00' })
    expect(p).toEqual({ start_date: '2026-01-01', end_date: '2026-01-31', cutoff_mode: 'absolute', decision_at: '2025-12-31T09:00:00Z' })
  })
})

describe('validation and presets', () => {
  it('rejects out-of-range and inverted ranges', () => {
    expect(validateFilters({ ...defaults, start: '2025-12-31' }, meta).start).toBeTruthy()
    expect(validateFilters({ ...defaults, start: '2026-01-10', end: '2026-01-05' }, meta).end).toMatch(/after start/)
    expect(validateFilters(defaults, meta)).toEqual({})
  })
  it('covers the month with week presets', () => {
    const p = rangePresets(meta)
    expect(p.map((x) => x.label)).toEqual(['Full month', 'Week 1', 'Week 2', 'Week 3', 'Week 4'])
    expect(p.at(-1)).toMatchObject({ start: '2026-01-22', end: '2026-01-31' })
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
  })
})

describe('formatting', () => {
  it('formats durations and signed values without inventing numbers', () => {
    expect(formatDuration(90)).toBe('1 h 30 min')
    expect(formatDuration(2880)).toBe('2 d 0 h')
    expect(formatSignedMW(-1234.4)).toBe('−1,234 MW')
    expect(formatSignedMW(null)).toBe('—')
  })
})
