import { LineChart as LineIcon } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { addDays, deliveryDates, londonWallToUtcIso, type Filters } from '../../lib/filters'
import { formatLocal, formatLocalShort, formatMW, formatSignedMW, LONDON_TZ } from '../../lib/format'
import type { ApiError } from '../../services/api'
import type { IntervalStatus, TimeseriesResponse } from '../../types/api'
import { Card, CardHeader } from '../ui/Card'
import { EmptyState, ErrorState, Skeleton } from '../ui/States'

// Validated pair (dataviz validator: CVD ΔE 24.9, normal 27.2). Forecast also differs by dash pattern.
const C = {
  forecast: '#2563eb',
  actual: '#059669',
  over: '#d97706',
  under: '#7c3aed',
  grid: '#eef0f3',
  axis: '#94a3b8',
  ink: '#0f172a',
}
const HOUR = 3_600_000

interface HourRow {
  t: number
  forecast: number | null
  actual: number | null
  error: number | null
  publish: string | null
  status: IntervalStatus
  range: [number, number] | null // central 80 % range for actual (from the error distribution)
}

interface Props {
  data?: TimeseriesResponse
  loading: boolean
  error?: ApiError
  onRetry: () => void
  filters: Filters
  selected?: string
  onSelect: (iso: string) => void
  className?: string
}

export function ForecastActualChart({ data, loading, error, onRetry, filters, selected, onSelect, className }: Props) {
  const [showError, setShowError] = useState(false)
  const [showRange, setShowRange] = useState(true)
  const [delStart, delEnd] = deliveryDates(filters)

  const { hours, halfHours, byHour } = useMemo(() => {
    const hours: HourRow[] = (data?.intervals ?? []).map((p) => ({
      t: Date.parse(p.start_time_utc),
      forecast: p.forecast_mw,
      actual: p.actual_mw,
      error: p.error_mw,
      publish: p.publish_time_utc,
      status: p.status,
      range: p.range_low_mw !== null && p.range_high_mw !== null ? [p.range_low_mw, p.range_high_mw] : null,
    }))
    const halfHours = (data?.actuals_half_hourly ?? []).map((a) => ({ t: Date.parse(a.start_time_utc), actual: a.actual_mw }))
    return { hours, halfHours, byHour: new Map(hours.map((h) => [h.t, h])) }
  }, [data])

  const domain = useMemo<[number, number]>(
    () => [Date.parse(londonWallToUtcIso(`${delStart}T00:00`)), Date.parse(londonWallToUtcIso(`${addDays(delEnd, 1)}T00:00`))],
    [delStart, delEnd],
  )
  const ticks = useMemo(() => buildTicks(delStart, delEnd), [delStart, delEnd])
  const short = delStart === delEnd || addDays(delStart, 1) === delEnd
  const hasRange = hours.some((h) => h.range)
  const hasAny = hours.some((h) => h.forecast !== null || h.actual !== null) || halfHours.length > 0
  const selectedMs = selected ? Date.parse(selected) : undefined

  return (
    <Card className={className}>
      <CardHeader
        icon={<LineIcon className="size-4" />}
        title="Forecast vs actual generation"
        subtitle={
          data
            ? `Selected forecast at ${data.cutoff.description} · ${formatLocal(data.period.start_utc)} → ${formatLocal(data.period.end_utc)}`
            : 'Loading period…'
        }
        action={
          <div className="flex flex-col items-end gap-1 sm:flex-row sm:gap-4">
            <Toggle checked={showRange} onChange={setShowRange} label="80% range" />
            <Toggle checked={showError} onChange={setShowError} label="Error bars" />
          </div>
        }
      />
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-5 pt-3 text-xs text-ink-muted" aria-hidden={!data}>
        <LegendKey dashed color={C.forecast} label="Selected forecast (hourly)" />
        <LegendKey color={C.actual} label="Actual generation (30-min)" />
        {showRange && hasRange && <LegendKey bar color={C.forecast} soft label="80% range for actual (from past errors)" />}
        {showError && (
          <>
            <LegendKey bar color={C.over} label="Over-forecast" />
            <LegendKey bar color={C.under} label="Under-forecast" />
          </>
        )}
        <span className="ml-auto hidden text-ink-subtle sm:inline">Click the chart to inspect an hour</span>
      </div>

      <div className="relative h-[340px] px-2 pt-2 pb-3">
        {error && !data ? (
          <ErrorState message={error.userMessage} onRetry={onRetry} className="h-full" />
        ) : !data ? (
          <Skeleton className="m-3 h-[310px]" />
        ) : !hasAny ? (
          <EmptyState
            className="h-full"
            title="No data for this period"
            description="Neither forecasts nor actuals are available for the selected delivery days."
          />
        ) : (
          <div
            className={`h-full transition-opacity ${loading ? 'opacity-50' : ''}`}
            role="img"
            aria-label={`Line chart of selected wind forecast and actual generation in MW, delivery ${delStart} to ${delEnd}. The interval table below lists every value.`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={hours}
                margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
                onClick={(state) => {
                  const label = Number(state?.activeLabel)
                  if (Number.isFinite(label)) onSelect(new Date(Math.floor(label / HOUR) * HOUR).toISOString().replace('.000Z', 'Z'))
                }}
                style={{ cursor: 'pointer' }}
              >
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis
                  dataKey="t"
                  type="number"
                  scale="time"
                  domain={domain}
                  ticks={ticks}
                  tickFormatter={(v: number) => tickLabel(v, short)}
                  tick={{ fontSize: 11, fill: C.axis }}
                  tickLine={false}
                  axisLine={{ stroke: '#e5e7eb' }}
                  allowDuplicatedCategory={false}
                />
                <YAxis
                  tickFormatter={(v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toLocaleString('en-GB')}k` : `${v}`)}
                  tick={{ fontSize: 11, fill: C.axis }}
                  tickLine={false}
                  axisLine={false}
                  width={44}
                  label={{ value: 'MW', angle: -90, position: 'insideLeft', offset: 4, fontSize: 11, fill: C.axis }}
                />
                <Tooltip
                  cursor={{ stroke: C.axis, strokeDasharray: '3 3' }}
                  isAnimationActive={false}
                  content={({ active, label }) => {
                    if (!active || label === undefined) return null
                    const row = byHour.get(Math.floor(Number(label) / HOUR) * HOUR)
                    return row ? <ChartTooltip row={row} /> : null
                  }}
                />
                {showError && <ReferenceLine y={0} stroke={C.axis} />}
                {showError && (
                  <Bar dataKey="error" isAnimationActive={false} maxBarSize={6} radius={[2, 2, 0, 0]}>
                    {hours.map((h) => (
                      <Cell key={h.t} fill={(h.error ?? 0) >= 0 ? C.over : C.under} fillOpacity={0.55} />
                    ))}
                  </Bar>
                )}
                {selectedMs !== undefined && <ReferenceLine x={selectedMs} stroke={C.ink} strokeOpacity={0.35} strokeDasharray="4 3" />}
                {showRange && hasRange && (
                  <Area
                    dataKey="range"
                    type="linear"
                    stroke="none"
                    fill={C.forecast}
                    fillOpacity={0.1}
                    isAnimationActive={false}
                    connectNulls={false}
                    activeDot={false}
                  />
                )}
                <Line
                  data={halfHours}
                  dataKey="actual"
                  type="linear"
                  stroke={C.actual}
                  strokeWidth={2}
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                  connectNulls={false}
                  name="Actual"
                />
                <Line
                  dataKey="forecast"
                  type="linear"
                  stroke={C.forecast}
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  dot={false}
                  activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }}
                  isAnimationActive={false}
                  connectNulls={false}
                  name="Selected forecast"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </Card>
  )
}

function ChartTooltip({ row }: { row: HourRow }) {
  return (
    <div className="min-w-56 rounded-lg border border-border bg-surface px-3 py-2.5 text-xs shadow-lg">
      <p className="font-semibold text-ink">{formatLocal(new Date(row.t).toISOString())}</p>
      <p className="text-ink-subtle">Delivery hour start</p>
      <dl className="mt-2 space-y-1 tabular">
        <TipRow swatch={C.forecast} dashed label="Forecast" value={formatMW(row.forecast)} />
        <TipRow swatch={C.actual} label="Actual" value={formatMW(row.actual)} />
        <TipRow label="Error" value={formatSignedMW(row.error)} strong />
        {row.range && <TipRow label="80% range" value={`${formatMW(row.range[0], false)}–${formatMW(row.range[1])}`} />}
      </dl>
      <p className="mt-2 border-t border-border pt-2 text-ink-muted">
        {row.publish ? `Published ${formatLocalShort(row.publish)}` : statusText(row.status)}
      </p>
    </div>
  )
}

function statusText(s: IntervalStatus): string {
  return s === 'MISSING_FORECAST' || s === 'MISSING_BOTH' ? 'No forecast published before the cutoff' : 'Actual not available'
}

function TipRow({ label, value, swatch, dashed, strong }: { label: string; value: string; swatch?: string; dashed?: boolean; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-6">
      <dt className="flex items-center gap-1.5 text-ink-muted">
        {swatch && (
          <svg width="14" height="4" aria-hidden>
            <line x1="0" y1="2" x2="14" y2="2" stroke={swatch} strokeWidth="2" strokeDasharray={dashed ? '4 2' : undefined} />
          </svg>
        )}
        {label}
      </dt>
      <dd className={strong ? 'font-semibold text-ink' : 'text-ink'}>{value}</dd>
    </div>
  )
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-muted select-none">
      <input type="checkbox" className="size-3.5 accent-ink" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

function LegendKey({ color, label, dashed, bar, soft }: { color: string; label: string; dashed?: boolean; bar?: boolean; soft?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      {bar ? (
        <span className="size-2.5 rounded-sm" style={{ background: color, opacity: soft ? 0.18 : 0.6 }} />
      ) : (
        <svg width="18" height="4" aria-hidden>
          <line x1="0" y1="2" x2="18" y2="2" stroke={color} strokeWidth="2" strokeDasharray={dashed ? '5 3' : undefined} />
        </svg>
      )}
      {label}
    </span>
  )
}

const dayFmt = new Intl.DateTimeFormat('en-GB', { timeZone: LONDON_TZ, day: 'numeric', month: 'short' })
const hourFmt = new Intl.DateTimeFormat('en-GB', { timeZone: LONDON_TZ, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })

function tickLabel(ms: number, short: boolean): string {
  const d = new Date(ms)
  const hm = hourFmt.format(d)
  if (!short) return dayFmt.format(d)
  return hm === '00:00' ? dayFmt.format(d) : hm
}

/** Ticks at London midnights (long ranges) or every 3/6 hours (one or two days). */
function buildTicks(start: string, end: string): number[] {
  const days = Math.round((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000) + 1
  const ticks: number[] = []
  if (days <= 2) {
    const step = days === 1 ? 3 : 6
    for (let d = 0; d < days; d++) {
      const day = addDays(start, d)
      for (let h = 0; h < 24; h += step) ticks.push(Date.parse(londonWallToUtcIso(`${day}T${String(h).padStart(2, '0')}:00`)))
    }
    ticks.push(Date.parse(londonWallToUtcIso(`${addDays(end, 1)}T00:00`)))
    return ticks
  }
  const every = days <= 10 ? 1 : days <= 20 ? 2 : 3
  for (let d = 0; d <= days; d += every) ticks.push(Date.parse(londonWallToUtcIso(`${addDays(start, d)}T00:00`)))
  return ticks
}
