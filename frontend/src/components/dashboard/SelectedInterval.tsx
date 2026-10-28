import { History } from 'lucide-react'
import type { ReactNode } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi } from '../../hooks/useApi'
import { cn } from '../../lib/cn'
import { formatDuration, formatLocal, formatLocalShort, formatMW, formatSignedMW, formatUtc, isNum, LONDON_TZ } from '../../lib/format'
import { api } from '../../services/api'
import type { AnalysisParams, ForecastHistoryResponse } from '../../types/api'
import { Badge } from '../ui/Badge'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { EmptyState, ErrorState, Skeleton } from '../ui/States'

const C = { forecast: '#2563eb', late: '#94a3b8', actual: '#059669', cutoff: '#0f172a', grid: '#eef0f3', axis: '#94a3b8' }

interface Props {
  params: AnalysisParams
  startTimeUtc?: string
  className?: string
}

export function SelectedInterval({ params, startTimeUtc, className }: Props) {
  const q = useApi(
    (signal) =>
      startTimeUtc ? api.forecastHistory(params, startTimeUtc, signal) : Promise.reject(new Error('no selection')),
    JSON.stringify([params, startTimeUtc]),
  )
  const h = q.data?.start_time_utc === startTimeUtc ? q.data : undefined

  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader
        icon={<History className="size-4" />}
        title="Selected interval"
        subtitle={startTimeUtc ? `Delivery hour starting ${formatLocal(startTimeUtc)}` : 'Click a chart point or table row'}
      />
      <CardBody className="flex-1 pt-4">
        {!startTimeUtc ? (
          <EmptyState title="No interval selected" description="Select a delivery hour to see which forecast was used." />
        ) : q.error && !h ? (
          <ErrorState message={q.error.userMessage} onRetry={q.reload} />
        ) : !h ? (
          <div className="space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : (
          <HistoryDetail h={h} loading={q.loading} />
        )}
      </CardBody>
    </Card>
  )
}

function HistoryDetail({ h, loading }: { h: ForecastHistoryResponse; loading: boolean }) {
  const sel = h.selected
  const error = sel && isNum(h.actual_mw) ? sel.forecast_mw - h.actual_mw : null

  return (
    <div className={cn('space-y-5 transition-opacity', loading && 'opacity-60')}>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <Fact label="Delivery start" sub={formatUtc(h.start_time_utc)}>
          {formatLocal(h.start_time_utc)}
        </Fact>
        <Fact label="Decision cutoff" sub={h.cutoff.description}>
          {formatLocal(h.cutoff_utc)}
        </Fact>
        <Fact label="Selected forecast">
          {sel ? <span className="text-forecast">{formatMW(sel.forecast_mw)}</span> : <Badge tone="warn">None eligible</Badge>}
        </Fact>
        <Fact label="Actual generation">
          <span className="text-actual">{formatMW(h.actual_mw)}</span>
        </Fact>
        <Fact label="Forecast published" sub={sel ? `${formatDuration(sel.minutes_before_cutoff)} before cutoff` : undefined}>
          {sel ? formatLocal(sel.publish_time_utc) : '—'}
        </Fact>
        <Fact label="Error (forecast − actual)" sub={sel ? `Forecast made ${formatDuration(sel.horizon_minutes)} ahead` : undefined}>
          <span className={isNum(error) ? (error > 0 ? 'text-over' : error < 0 ? 'text-under' : '') : ''}>{formatSignedMW(error)}</span>
        </Fact>
        <Fact label="Eligible versions" sub={`${h.total_versions - h.eligible_versions} published too late to use`}>
          {h.eligible_versions} of {h.total_versions}
        </Fact>
      </dl>

      {h.versions.length > 0 ? (
        <>
          <HistoryChart h={h} />
          <VersionTable h={h} />
        </>
      ) : (
        <EmptyState title="No forecasts found" description="Elexon returned no WINDFOR versions for this delivery hour." />
      )}
    </div>
  )
}

function Fact({ label, sub, children }: { label: string; sub?: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-ink-subtle">{label}</dt>
      <dd className="mt-0.5 font-semibold tabular">{children}</dd>
      {sub && <dd className="truncate text-xs text-ink-muted" title={sub}>{sub}</dd>}
    </div>
  )
}

const shortFmt = new Intl.DateTimeFormat('en-GB', { timeZone: LONDON_TZ, day: 'numeric', month: 'short', hour: '2-digit', hourCycle: 'h23' })

/** How the forecast for this hour evolved across publications, with the cutoff and the eventual actual. */
function HistoryChart({ h }: { h: ForecastHistoryResponse }) {
  const pts = h.versions.map((v) => ({ t: Date.parse(v.publish_time_utc), mw: v.forecast_mw, eligible: v.eligible }))
  const eligible = pts.filter((p) => p.eligible)
  // The late series starts at the last eligible point, so the step line stays continuous.
  const late = [...eligible.slice(-1), ...pts.filter((p) => !p.eligible)]
  const cutoff = Date.parse(h.cutoff_utc)
  const values = [...pts.map((p) => p.mw), ...(isNum(h.actual_mw) ? [h.actual_mw] : [])]
  const pad = Math.max(200, (Math.max(...values) - Math.min(...values)) * 0.15)
  // Explicit, evenly spaced ticks: each Line carries its own data, so auto ticks only see the first series.
  const tMin = Math.min(...pts.map((p) => p.t), cutoff)
  const tMax = Math.max(...pts.map((p) => p.t), cutoff)
  const ticks = Array.from({ length: 4 }, (_, i) => Math.round(tMin + ((tMax - tMin) * i) / 3))

  return (
    <figure>
      <figcaption className="mb-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
        <span className="font-medium text-ink">Forecast by publication time</span>
        <Key color={C.forecast} label="Eligible" />
        <Key color={C.late} label="Not usable (too late)" dashed />
        <Key color={C.actual} label="Actual" dashed />
      </figcaption>
      <div className="h-44" role="img" aria-label="Step chart of forecast versions by publication time; the version table below lists the values.">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart margin={{ top: 14, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={[tMin, tMax]}
              ticks={ticks}
              tickFormatter={(v: number) => shortFmt.format(new Date(v))}
              tick={{ fontSize: 10, fill: C.axis }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              allowDuplicatedCategory={false}
            />
            <YAxis
              domain={[Math.floor(Math.min(...values) - pad), Math.ceil(Math.max(...values) + pad)]}
              tickFormatter={(v: number) => `${(v / 1000).toLocaleString('en-GB', { maximumFractionDigits: 1 })}k`}
              tick={{ fontSize: 10, fill: C.axis }}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            <Tooltip
              isAnimationActive={false}
              content={({ active, payload }) => {
                const p = active ? (payload?.[0]?.payload as (typeof pts)[number] | undefined) : undefined
                if (!p) return null
                return (
                  <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-lg">
                    <p className="font-semibold">{formatMW(p.mw)}</p>
                    <p className="text-ink-muted">Published {formatLocal(new Date(p.t).toISOString())}</p>
                    <p className={p.eligible ? 'text-ok' : 'text-ink-subtle'}>{p.eligible ? 'Usable at decision time' : 'Too late (not used)'}</p>
                  </div>
                )
              }}
            />
            {isNum(h.actual_mw) && (
              <ReferenceLine y={h.actual_mw} stroke={C.actual} strokeDasharray="4 3" ifOverflow="extendDomain" />
            )}
            <ReferenceLine
              x={cutoff}
              stroke={C.cutoff}
              strokeOpacity={0.6}
              ifOverflow="extendDomain"
              label={{ value: 'Cutoff', position: 'top', fontSize: 10, fill: C.cutoff }}
            />
            <Line data={late} dataKey="mw" type="stepAfter" stroke={C.late} strokeWidth={2} strokeDasharray="4 3" dot={{ r: 2.5, fill: C.late, strokeWidth: 0 }} isAnimationActive={false} />
            <Line data={eligible} dataKey="mw" type="stepAfter" stroke={C.forecast} strokeWidth={2} dot={{ r: 3, fill: C.forecast, stroke: '#fff', strokeWidth: 1.5 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

function Key({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="16" height="4" aria-hidden>
        <line x1="0" y1="2" x2="16" y2="2" stroke={color} strokeWidth="2" strokeDasharray={dashed ? '4 2' : undefined} />
      </svg>
      {label}
    </span>
  )
}

function VersionTable({ h }: { h: ForecastHistoryResponse }) {
  return (
    <div>
      <p className="mb-2 text-xs font-medium text-ink">Publication history (Europe/London)</p>
      <div className="max-h-56 overflow-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-muted text-ink-muted">
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-medium">Published</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Forecast MW</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">vs cutoff</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {[...h.versions].reverse().map((v) => (
              <tr
                key={v.publish_time_utc}
                className={cn(
                  'border-t border-border',
                  v.selected && 'bg-forecast-soft font-semibold',
                  !v.eligible && 'text-ink-subtle',
                )}
              >
                <td className="px-3 py-1.5 tabular" title={formatUtc(v.publish_time_utc)}>
                  {formatLocalShort(v.publish_time_utc)}
                </td>
                <td className="px-3 py-1.5 text-right tabular">{formatMW(v.forecast_mw, false)}</td>
                <td className="px-3 py-1.5 text-right tabular">
                  {v.minutes_before_cutoff >= 0 ? `−${formatDuration(v.minutes_before_cutoff)}` : `+${formatDuration(-v.minutes_before_cutoff)}`}
                </td>
                <td className="px-3 py-1.5">
                  {v.selected ? (
                    <Badge tone="forecast">Selected</Badge>
                  ) : v.eligible ? (
                    <Badge tone="ok">Eligible</Badge>
                  ) : v.ineligible_reason === 'AFTER_DELIVERY_START' ? (
                    <Badge title="Published before the cutoff but after this hour began, so it is an observation rather than a forecast">
                      After hour began
                    </Badge>
                  ) : (
                    <Badge>After cutoff</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
