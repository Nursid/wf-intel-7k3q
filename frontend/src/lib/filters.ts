import type { AnalysisParams, CutoffMode, MetaResponse } from '../types/api'
import { LONDON_TZ } from './format'

/** Dashboard filter state. Wall-clock times are Europe/London; conversion to UTC happens on the way to the API. */
export interface Filters {
  start: string // yyyy-mm-dd
  end: string
  mode: CutoffMode
  offset: number // days before delivery (relative)
  time: string // HH:MM (relative)
  decision: string // yyyy-mm-ddTHH:MM London wall time (absolute)
}

export const DAY_OFFSET_OPTIONS = [
  { value: 0, label: 'Same day (D-0)', phrase: 'the delivery day' },
  { value: 1, label: 'Day before (D-1)', phrase: 'the day before delivery' },
  { value: 2, label: '2 days before (D-2)', phrase: 'two days before delivery' },
  { value: 3, label: '3 days before (D-3)', phrase: 'three days before delivery' },
]

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/
const DATE = /^\d{4}-\d{2}-\d{2}$/
const WALL = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/

export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

export function defaultFilters(meta: MetaResponse): Filters {
  const c = meta.default_cutoff
  return {
    start: meta.available_start_date,
    end: meta.available_end_date,
    mode: 'relative',
    offset: c.day_offset ?? 1,
    time: c.local_time ?? '09:00',
    decision: `${addDays(meta.available_start_date, -1)}T${c.local_time ?? '09:00'}`,
  }
}

/** Read filters from the URL, falling back to defaults for anything missing or malformed. */
export function filtersFromSearch(sp: URLSearchParams, defaults: Filters): Filters {
  const pick = (k: string, re: RegExp, d: string) => {
    const v = sp.get(k)
    return v && re.test(v) ? v : d
  }
  const offset = Number(sp.get('offset'))
  return {
    start: pick('from', DATE, defaults.start),
    end: pick('to', DATE, defaults.end),
    mode: sp.get('mode') === 'absolute' ? 'absolute' : 'relative',
    offset: sp.has('offset') && Number.isInteger(offset) && offset >= 0 && offset <= 7 ? offset : defaults.offset,
    time: pick('time', HHMM, defaults.time),
    decision: pick('decision', WALL, defaults.decision),
  }
}

/** Only non-default values go into the URL, so links stay short. */
export function filtersToSearch(f: Filters, defaults: Filters): URLSearchParams {
  const sp = new URLSearchParams()
  if (f.start !== defaults.start) sp.set('from', f.start)
  if (f.end !== defaults.end) sp.set('to', f.end)
  if (f.mode === 'absolute') {
    sp.set('mode', 'absolute')
    sp.set('decision', f.decision)
  } else {
    if (f.offset !== defaults.offset) sp.set('offset', String(f.offset))
    if (f.time !== defaults.time) sp.set('time', f.time)
  }
  return sp
}

export function validateFilters(f: Filters, meta: MetaResponse): Partial<Record<keyof Filters, string>> {
  const errors: Partial<Record<keyof Filters, string>> = {}
  const lo = meta.available_start_date
  const hi = meta.available_end_date
  if (!DATE.test(f.start) || f.start < lo || f.start > hi) errors.start = `Choose a date in ${lo} – ${hi}`
  if (!DATE.test(f.end) || f.end < lo || f.end > hi) errors.end = `Choose a date in ${lo} – ${hi}`
  if (!errors.start && !errors.end && f.end < f.start) errors.end = 'End must be on or after start'
  if (f.mode === 'relative' && !HHMM.test(f.time)) errors.time = 'Use HH:MM (24h)'
  if (f.mode === 'absolute' && !WALL.test(f.decision)) errors.decision = 'Enter a decision date and time'
  return errors
}

export function toAnalysisParams(f: Filters): AnalysisParams {
  const base = { start_date: f.start, end_date: f.end, cutoff_mode: f.mode }
  return f.mode === 'absolute'
    ? { ...base, decision_at: londonWallToUtcIso(f.decision) }
    : { ...base, cutoff_day_offset: f.offset, cutoff_time: f.time }
}

export function sameFilters(a: Filters, b: Filters): boolean {
  return (Object.keys(a) as (keyof Filters)[]).every((k) => a[k] === b[k])
}

/** Quick ranges within the available month: full month and four weeks (the last absorbs the remainder). */
export function rangePresets(meta: MetaResponse): { label: string; start: string; end: string }[] {
  const lo = meta.available_start_date
  const hi = meta.available_end_date
  const presets = [{ label: 'Full month', start: lo, end: hi }]
  for (let w = 0; w < 4; w++) {
    const start = addDays(lo, w * 7)
    if (start > hi) break
    const end = w === 3 ? hi : addDays(start, 6) > hi ? hi : addDays(start, 6)
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

/** Start (inclusive) and end (exclusive) of the selected London days, in UTC ms. */
export function periodBoundsUtc(f: Filters): [number, number] {
  return [Date.parse(londonWallToUtcIso(`${f.start}T00:00`)), Date.parse(londonWallToUtcIso(`${addDays(f.end, 1)}T00:00`))]
}
