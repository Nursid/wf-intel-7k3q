import { Sigma } from 'lucide-react'
import { formatInt, formatMW, formatPct, formatSignedMW } from '../../lib/format'
import type { Metrics } from '../../types/api'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { Skeleton } from '../ui/States'

export function AccuracyPanel({ metrics, className }: { metrics?: Metrics; className?: string }) {
  const rows = metrics && [
    {
      name: 'MAE',
      full: 'Mean Absolute Error',
      value: formatMW(metrics.mae_mw),
      text: 'Typical size of a miss, in either direction. Lower is better.',
    },
    {
      name: 'RMSE',
      full: 'Root Mean Squared Error',
      value: formatMW(metrics.rmse_mw),
      text: 'Like MAE but penalises large misses more. A gap well above MAE signals occasional big errors.',
    },
    {
      name: 'MBE',
      full: 'Mean Bias Error',
      value: formatSignedMW(metrics.mbe_mw),
      text: 'Positive = forecasts overestimated generation on average; negative = underestimated.',
    },
    {
      name: 'WAPE',
      full: 'Weighted Absolute Percentage Error',
      value: metrics.wape_pct === null && metrics.matched_count > 0 ? 'Unavailable' : formatPct(metrics.wape_pct),
      text: 'Total absolute error as a share of total actual generation. Unavailable when actual totals zero.',
    },
  ]

  return (
    <Card className={className}>
      <CardHeader icon={<Sigma className="size-4" />} title="Accuracy metrics" subtitle="Forecast − actual, matched hours only" />
      <CardBody className="pt-4">
        {!rows ? (
          <div className="space-y-5">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <>
            <dl className="divide-y divide-border">
              {rows.map((r) => (
                <div key={r.name} className="py-3 first:pt-0">
                  <div className="flex items-baseline justify-between gap-3">
                    <dt className="text-sm font-semibold">
                      {r.name} <span className="font-normal text-ink-muted">· {r.full}</span>
                    </dt>
                    <dd className="text-base font-semibold whitespace-nowrap tabular">{r.value}</dd>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-ink-muted">{r.text}</p>
                </div>
              ))}
            </dl>
            <p className="mt-3 rounded-lg bg-surface-muted px-3 py-2 text-xs leading-relaxed text-ink-muted">
              Based on <strong className="font-semibold text-ink">{formatInt(metrics.matched_count)}</strong> matched hours.{' '}
              {formatInt(metrics.missing_forecast_count)} without an eligible forecast, {formatInt(metrics.missing_actual_count)}{' '}
              without an actual. These are excluded, not treated as zero.
            </p>
          </>
        )}
      </CardBody>
    </Card>
  )
}
