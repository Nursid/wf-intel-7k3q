import type { AnalysisParams, MetaResponse } from '../types/api'
import { LONDON_TZ } from './format'

/**
 * Dashboard filter state. Scope is defined by *decision* dates (purchase decisions in January 2026);
 * delivery days follow as decision date + offset. Wall-clock times are Europe/London.
 */
export interface Filters {
  start: string // first decision day, yyyy-mm-dd
  end: string // last decision day
  offset: number // decide this many days before delivery (1 = day-ahead)
  time: string // decision time HH:MM
}

export const DAY_OFFSET_OPTIONS = [
  { value: 1, label: 'Next day (day-ahead)', phrase: 'the day before delivery' },
  { value: 0, label: 'Same day', phrase: 'the delivery day itself' },
  { value: 2, label: 'In 2 days', phrase: 'two days before delivery' },
  { value: 3, label: 'In 3 days', phrase: 'three days before delivery' },
]

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/
const DATE = /^\d{4}-\d{2}-\d{2}$/

export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

export function defaultFilters(meta: MetaResponse): Filters {
  return {
    start: meta.decision_start_date,
    end: meta.decision_end_date,
    offset: meta.default_cutoff.day_offset,
    time: meta.default_cutoff.local_time,
  }
}

/** Delivery days covered by the selected decision days. */
export function deliveryDates(f: Filters): [string, string] {
  return [addDays(f.start, f.offset), addDays(f.end, f.offset)]
}

/** Read filters from the URL, falling back to defaults for anything missing or malformed. */
export function filtersFromSearch(sp: URLSearchParams, defaults: Filters, maxOffset = 3): Filters {
  const pick = (k: string, re: RegExp, d: string) => {
    const v = sp.get(k)
    return v && re.test(v) ? v : d
  }
  const offset = Number(sp.get('offset'))
  return {
    start: pick('from', DATE, defaults.start),
    end: pick('to', DATE, defaults.end),
    offset: sp.has('offset') && Number.isInteger(offset) && offset >= 0 && offset <= maxOffset ? offset : defaults.offset,
    time: pick('time', HHMM, defaults.time),
  }
}

/** Only non-default values go into the URL, so links stay short. */
export function filtersToSearch(f: Filters, defaults: Filters): URLSearchParams {
  const sp = new URLSearchParams()
  if (f.start !== defaults.start) sp.set('from', f.start)
  if (f.end !== defaults.end) sp.set('to', f.end)
  if (f.offset !== defaults.offset) sp.set('offset', String(f.offset))
  if (f.time !== defaults.time) sp.set('time', f.time)
  return sp
}

export function validateFilters(f: Filters, meta: MetaResponse): Partial<Record<keyof Filters, string>> {
  const errors: Partial<Record<keyof Filters, string>> = {}
  const lo = meta.decision_start_date
  const hi = meta.decision_end_date
  if (!DATE.test(f.start) || f.start < lo || f.start > hi) errors.start = `Decisions must be in ${lo} – ${hi}`
  if (!DATE.test(f.end) || f.end < lo || f.end > hi) errors.end = `Decisions must be in ${lo} – ${hi}`
  if (!errors.start && !errors.end && f.end < f.start) errors.end = 'End must be on or after start'
  if (!HHMM.test(f.time)) errors.time = 'Use HH:MM (24h)'
  return errors
}

export function toAnalysisParams(f: Filters): AnalysisParams {
  return { decision_start_date: f.start, decision_end_date: f.end, cutoff_day_offset: f.offset, cutoff_time: f.time }
}

export function sameFilters(a: Filters, b: Filters): boolean {
  return (Object.keys(a) as (keyof Filters)[]).every((k) => a[k] === b[k])
}

/** Quick decision-date ranges: full month and four weeks (the last absorbs the remainder). */
export function rangePresets(meta: MetaResponse): { label: string; start: string; end: string }[] {
  const lo = meta.decision_start_date
  const hi = meta.decision_end_date
  const presets = [{ label: 'All of January', start: lo, end: hi }]
  for (let w = 0; w < 4; w++) {
    const start = addDays(lo, w * 7)
    if (start > hi) break
    const end = w === 3 || addDays(start, 6) > hi ? hi : addDays(start, 6)
    presets.push({ label: `Week ${w + 1}`, start, end })
  }
  return presets
}

// ---------------------------------------------------------------- Europe/London <-> UTC

const partsFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: LONDON_TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

function londonParts(ms: number): Record<string, number> {
  const out: Record<string, number> = {}
  for (const p of partsFmt.formatToParts(new Date(ms))) if (p.type !== 'literal') out[p.type] = Number(p.value)
  return out
}

/** London UTC offset in minutes at an instant (0 in GMT, 60 in BST). */
function londonOffsetMinutes(ms: number): number {
  const p = londonParts(ms)
  const asUtc = Date.UTC(p.year!, p.month! - 1, p.day!, p.hour!, p.minute!)
  return Math.round((asUtc - Math.floor(ms / 60000) * 60000) / 60000)
}

/** "2026-01-01T09:00" (London wall time) -> "2026-01-01T09:00:00Z" */
export function londonWallToUtcIso(wall: string): string {
  const [d = '', t = '00:00'] = wall.split('T')
  const [y, m, day] = d.split('-').map(Number)
  const [hh, mm] = t.split(':').map(Number)
  const guess = Date.UTC(y!, m! - 1, day!, hh!, mm!)
  let utc = guess - londonOffsetMinutes(guess) * 60000
  const check = londonOffsetMinutes(utc)
  if (guess - check * 60000 !== utc) utc = guess - check * 60000
  return new Date(utc).toISOString().replace('.000Z', 'Z')
}

/** Start (inclusive) and end (exclusive) of the covered delivery days, in UTC ms. */
export function periodBoundsUtc(f: Filters): [number, number] {
  const [ds, de] = deliveryDates(f)
  return [Date.parse(londonWallToUtcIso(`${ds}T00:00`)), Date.parse(londonWallToUtcIso(`${addDays(de, 1)}T00:00`))]
}
