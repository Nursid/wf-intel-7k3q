// Presentation-only formatting. Delivery times are shown in Europe/London with an explicit GMT/BST label.

export const LONDON_TZ = 'Europe/London'
const DASH = '—'

const mwFmt = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })
const pctFmt = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1, minimumFractionDigits: 1 })
const intFmt = new Intl.NumberFormat('en-GB')

export const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v)

export function formatMW(v: number | null | undefined, withUnit = true): string {
  if (!isNum(v)) return DASH
  return withUnit ? `${mwFmt.format(v)} MW` : mwFmt.format(v)
}

export function formatSignedMW(v: number | null | undefined, withUnit = true): string {
  if (!isNum(v)) return DASH
  const sign = v > 0 ? '+' : v < 0 ? '−' : ''
  return `${sign}${formatMW(Math.abs(v), withUnit)}`
}

export function formatPct(v: number | null | undefined): string {
  return isNum(v) ? `${pctFmt.format(v)}%` : DASH
}

export function formatInt(v: number | null | undefined): string {
  return isNum(v) ? intFmt.format(v) : DASH
}

const localDateTime = new Intl.DateTimeFormat('en-GB', {
  timeZone: LONDON_TZ,
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZoneName: 'short',
})

const localShort = new Intl.DateTimeFormat('en-GB', {
  timeZone: LONDON_TZ,
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

const localDate = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' })

/** "12 Jan 2026, 09:14 GMT" */
export function formatLocal(iso: string | null | undefined): string {
  if (!iso) return DASH
  return localDateTime.format(new Date(iso))
}

/** "12 Jan, 09:14" (no timezone label; use where a column header states the zone) */
export function formatLocalShort(iso: string | null | undefined): string {
  if (!iso) return DASH
  return localShort.format(new Date(iso))
}

/** "2026-01-12 09:14 UTC" */
export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return DASH
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`
}

/** A yyyy-mm-dd calendar date, e.g. "1 Jan 2026" */
export function formatDate(isoDate: string | null | undefined): string {
  if (!isoDate) return DASH
  return localDate.format(new Date(`${isoDate}T00:00:00Z`))
}

export function formatDateRange(start: string, end: string): string {
  return start === end ? formatDate(start) : `${formatDate(start)} – ${formatDate(end)}`
}

/** 90 -> "1 h 30 min", 2880 -> "2 d 0 h" */
export function formatDuration(minutes: number | null | undefined): string {
  if (!isNum(minutes)) return DASH
  const sign = minutes < 0 ? '−' : ''
  const m = Math.round(Math.abs(minutes))
  const d = Math.floor(m / 1440)
  const h = Math.floor((m % 1440) / 60)
  const mm = m % 60
  if (d) return `${sign}${d} d ${h} h`
  if (h) return `${sign}${h} h${mm ? ` ${mm} min` : ''}`
  return `${sign}${mm} min`
}

/** "3 minutes ago" style relative time for freshness indicators. */
export function formatRelative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return DASH
  const diff = Math.round((now - new Date(iso).getTime()) / 1000)
  const rtf = new Intl.RelativeTimeFormat('en-GB', { numeric: 'auto' })
  const steps: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, 'second'],
    [60, 'minute'],
    [24, 'hour'],
    [30, 'day'],
    [12, 'month'],
  ]
  let value = diff
  for (const [size, unit] of steps) {
    if (Math.abs(value) < size) return rtf.format(-value, unit)
    value = Math.round(value / size)
  }
  return rtf.format(-value, 'year')
}
