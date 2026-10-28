import { Activity, ArrowDownRight, ArrowUpRight, Gauge, Minus, Target, Wind } from 'lucide-react'
import type { ReactNode } from 'react'
import { formatInt, formatMW, formatPct, formatSignedMW, isNum } from '../../lib/format'
import type { Metrics } from '../../types/api'
import { Badge } from '../ui/Badge'
import { Card } from '../ui/Card'
import { InfoTip } from '../ui/InfoTip'
import { Skeleton } from '../ui/States'

const NO_MATCH = 'Unavailable: no delivery hour in this selection has both an eligible forecast and an actual.'

export function KpiCards({ metrics, loading }: { metrics?: Metrics; loading: boolean }) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <Card key={i} className="p-5">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-3 h-8 w-28" />
            <Skeleton className="mt-3 h-3 w-32" />
          </Card>
        ))}
      </div>
    )
  }
  const m = metrics
  const n = `${formatInt(m.matched_count)} matched hours`
  const bias = m.mbe_mw

  return (
    <div className={`grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5 ${loading ? 'opacity-60 transition-opacity' : ''}`} aria-busy={loading}>
      <Kpi
        icon={<Wind className="size-4" />}
        accent="bg-forecast"
        label="Selected forecast"
        value={formatMW(m.mean_forecast_mw)}
        sub={`Mean of ${n}`}
        tip={isNum(m.mean_forecast_mw) ? 'Average MW of the forecasts selected at the decision cutoff.' : NO_MATCH}
      />
      <Kpi
        icon={<Activity className="size-4" />}
        accent="bg-actual"
        label="Actual generation"
        value={formatMW(m.mean_actual_mw)}
        sub={`Mean of the same ${n}`}
        tip={isNum(m.mean_actual_mw) ? 'Average outturn (FUELHH WIND) over the same matched hours.' : NO_MATCH}
      />
      <Kpi
        icon={<Target className="size-4" />}
        label="Mean absolute error"
        value={formatMW(m.mae_mw)}
        sub={isNum(m.max_abs_error_mw) ? `Largest miss ${formatMW(m.max_abs_error_mw)}` : 'No matched hours'}
        tip={isNum(m.mae_mw) ? 'Average size of the forecast error, ignoring direction. Lower is better.' : NO_MATCH}
      />
      <Kpi
        icon={<Gauge className="size-4" />}
        label="Forecast bias (MBE)"
        value={formatSignedMW(bias)}
        badge={
          !isNum(bias) ? undefined : bias > 0 ? (
            <Badge tone="over" icon={<ArrowUpRight className="size-3" aria-hidden />}>
              Over-forecast
            </Badge>
          ) : bias < 0 ? (
            <Badge tone="under" icon={<ArrowDownRight className="size-3" aria-hidden />}>
              Under-forecast
            </Badge>
          ) : (
            <Badge icon={<Minus className="size-3" aria-hidden />}>No bias</Badge>
          )
        }
        sub="Mean of forecast − actual"
        tip={
          isNum(bias)
            ? 'Positive: forecasts were higher than actual on average. Negative: lower.'
            : NO_MATCH
        }
      />
      <Kpi
        icon={<Activity className="size-4" />}
        label="Data coverage"
        value={formatPct(m.coverage_pct)}
        sub={`${formatInt(m.matched_count)} / ${formatInt(m.expected_count)} hours matched`}
        badge={
          isNum(m.coverage_pct) && m.coverage_pct < 100 ? (
            <Badge tone="warn" dot>
              Gaps
            </Badge>
          ) : undefined
        }
        tip="Matched delivery hours ÷ expected hourly intervals in the selected period. Missing values are excluded, never zero-filled."
        className="col-span-2 md:col-span-1"
      />
    </div>
  )
}

interface KpiProps {
  icon: ReactNode
  label: string
  value: string
  sub: string
  tip: string
  badge?: ReactNode
  accent?: string
  className?: string
}

function Kpi({ icon, label, value, sub, tip, badge, accent, className }: KpiProps) {
  return (
    <Card className={`relative flex flex-col overflow-hidden p-5 ${className ?? ''}`}>
      {accent && <span aria-hidden className={`absolute inset-y-0 left-0 w-1 ${accent}`} />}
      <div className="flex items-center gap-1.5 text-xs font-medium text-ink-muted">
        <span className="text-ink-subtle">{icon}</span>
        {label}
        <InfoTip>{tip}</InfoTip>
      </div>
      <p className="mt-3 text-[28px] leading-8 font-semibold tracking-tight tabular">{value}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {badge}
        <span className="text-xs text-ink-muted">{sub}</span>
      </div>
    </Card>
  )
}
