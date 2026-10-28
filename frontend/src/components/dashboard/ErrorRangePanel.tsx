import { Ruler } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatInt, formatMW, formatPct } from '../../lib/format'
import type { ErrorDistribution } from '../../types/api'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { InfoTip } from '../ui/InfoTip'
import { EmptyState, Skeleton } from '../ui/States'

// Same validated over/under pair as the main chart (dataviz validator: ΔE 34.6).
const C = { over: '#d97706', under: '#7c3aed', axis: '#94a3b8', grid: '#eef0f3', ink: '#0f172a', band: '#2563eb' }

/** "4,800 MW below" / "600 MW above" the forecast. */
function rel(v: number): string {
  if (Math.round(v) === 0) return 'at'
  return `${formatMW(Math.abs(v))} ${v < 0 ? 'below' : 'above'}`
}

interface Props {
  dist?: ErrorDistribution | null
  loading: boolean
  className?: string
}

export function ErrorRangePanel({ dist, loading, className }: Props) {
  return (
    <Card className={className}>
      <CardHeader
        icon={<Ruler className="size-4" />}
        title="Error range: plan around the forecast"
        subtitle="How far actual wind generation landed from the forecast available at decision time"
        action={
          <InfoTip label="About these ranges">
            Empirical ranges from the matched hours of the selected period (in-sample). They describe how past forecasts
            performed. They are not a probabilistic forecast, and they say nothing about demand or prices.
          </InfoTip>
        }
      />
      <CardBody className={`transition-opacity ${loading ? 'opacity-60' : ''}`}>
        {dist === undefined ? (
          <div className="grid gap-6 lg:grid-cols-12">
            <Skeleton className="h-48 lg:col-span-5" />
            <Skeleton className="h-48 lg:col-span-7" />
          </div>
        ) : dist === null ? (
          <EmptyState
            title="No matched hours"
            description="No delivery hour in this selection has both an eligible forecast and an actual, so no error range can be computed."
          />
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <Summary dist={dist} />
            <Histogram dist={dist} />
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function Summary({ dist }: { dist: ErrorDistribution }) {
  const r80 = dist.actual_ranges.find((r) => r.coverage_pct === 80) ?? dist.actual_ranges[0]!
  const lo = Math.min(...dist.actual_ranges.map((r) => r.low_mw), 0)
  const hi = Math.max(...dist.actual_ranges.map((r) => r.high_mw), 0)
  const span = hi - lo || 1
  const x = (v: number) => `${((v - lo) / span) * 100}%`

  return (
    <div className="space-y-5 lg:col-span-5">
      <p className="text-base leading-relaxed text-ink">
        In <strong className="font-semibold">{r80.coverage_pct}% of hours</strong>, actual wind was between{' '}
        <strong className="font-semibold text-under">{rel(r80.low_mw)}</strong> and{' '}
        <strong className="font-semibold text-over">{rel(r80.high_mw)}</strong> the forecast.
      </p>

      <div>
        <div className="grid grid-cols-[3.25rem_1fr] gap-3 text-[11px] text-ink-subtle">
          <span />
          <div className="relative mb-1 h-4">
            <span className="absolute -translate-x-1/2 font-medium whitespace-nowrap text-ink" style={{ left: x(0) }}>
              Forecast
            </span>
          </div>
        </div>
        <div className="space-y-2.5">
          {dist.actual_ranges.map((r) => (
            <div key={r.coverage_pct} className="grid grid-cols-[3.25rem_1fr] items-center gap-3 text-xs">
              <span className="font-medium text-ink-muted tabular">{r.coverage_pct}%</span>
              <div className="relative h-6 rounded bg-surface-muted" role="img" aria-label={`${r.coverage_pct}% of hours: ${rel(r.low_mw)} to ${rel(r.high_mw)} the forecast`}>
                <span
                  className="absolute inset-y-1 rounded-sm bg-forecast/20 ring-1 ring-forecast/40 ring-inset"
                  style={{ left: x(r.low_mw), width: `calc(${x(r.high_mw)} - ${x(r.low_mw)})` }}
                />
                <span aria-hidden className="absolute inset-y-0 w-0.5 bg-ink" style={{ left: x(0) }} />
              </div>
            </div>
          ))}
          <div className="grid grid-cols-[3.25rem_1fr] gap-3 text-[11px] text-ink-subtle tabular">
            <span />
            <div className="flex justify-between">
              <span>← {formatMW(Math.abs(lo))} below</span>
              <span>{formatMW(hi)} above →</span>
            </div>
          </div>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {dist.within.map((w) => (
          <div key={w.threshold_mw} className="rounded-lg bg-surface-muted px-3 py-2">
            <dt className="text-[11px] text-ink-subtle">Within ±{formatInt(w.threshold_mw)} MW</dt>
            <dd className="text-sm font-semibold tabular">{formatPct(w.pct)}</dd>
          </div>
        ))}
      </dl>

      <p className="text-xs leading-relaxed text-ink-muted">
        The forecast was <strong className="font-medium text-over">above actual in {formatPct(dist.over_forecast_pct)}</strong> of
        hours. Median error {formatMW(dist.percentiles_mw.p50)}. Based on {formatInt(dist.n)} matched hours.
      </p>
    </div>
  )
}

function Histogram({ dist }: { dist: ErrorDistribution }) {
  const data = dist.histogram.map((b) => ({ mid: (b.low_mw + b.high_mw) / 2, ...b }))
  return (
    <figure className="lg:col-span-7">
      <figcaption className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
        <span className="font-medium text-ink">Distribution of forecast − actual</span>
        <Key color={C.under} label="Under-forecast (actual higher)" />
        <Key color={C.over} label="Over-forecast (actual lower)" />
      </figcaption>
      <div className="h-60" role="img" aria-label={`Histogram of hourly forecast errors in ${formatMW(dist.bin_width_mw)} bins`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 16, left: 0 }} barCategoryGap={1}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis
              dataKey="mid"
              type="number"
              domain={[data[0]!.low_mw, data.at(-1)!.high_mw]}
              tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${(v / 1000).toLocaleString('en-GB')}k`}
              tick={{ fontSize: 11, fill: C.axis }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              label={{ value: 'Forecast − actual (MW)', position: 'insideBottom', offset: -10, fontSize: 11, fill: C.axis }}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: C.axis }} tickLine={false} axisLine={false} width={36} />
            <Tooltip
              cursor={{ fill: 'rgba(15,23,42,0.04)' }}
              isAnimationActive={false}
              content={({ active, payload }) => {
                const b = active ? (payload?.[0]?.payload as (typeof data)[number] | undefined) : undefined
                if (!b) return null
                return (
                  <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-lg">
                    <p className="font-semibold tabular">
                      {formatMW(b.low_mw)} to {formatMW(b.high_mw)}
                    </p>
                    <p className="text-ink-muted">
                      {formatInt(b.count)} hours ({formatPct((b.count / dist.n) * 100)})
                    </p>
                  </div>
                )
              }}
            />
            <ReferenceLine x={0} stroke={C.ink} strokeOpacity={0.6} />
            <Bar dataKey="count" isAnimationActive={false} radius={[3, 3, 0, 0]}>
              {data.map((b) => (
                <Cell key={b.low_mw} fill={b.mid >= 0 ? C.over : C.under} fillOpacity={0.75} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

function Key({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="size-2.5 rounded-sm" style={{ background: color, opacity: 0.75 }} />
      {label}
    </span>
  )
}
