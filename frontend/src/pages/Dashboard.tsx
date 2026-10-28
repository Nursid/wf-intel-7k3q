import { useMemo } from 'react'
import { ForecastActualChart } from '../components/charts/ForecastActualChart'
import { AccuracyPanel } from '../components/dashboard/AccuracyPanel'
import { DataQualityPanel } from '../components/dashboard/DataQualityPanel'
import { KpiCards } from '../components/dashboard/KpiCards'
import { SelectedInterval } from '../components/dashboard/SelectedInterval'
import { FilterBar } from '../components/filters/FilterBar'
import { AppShell } from '../components/layout/AppShell'
import { Header } from '../components/layout/Header'
import { Section } from '../components/layout/Section'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { ErrorState, Skeleton } from '../components/ui/States'
import { IntervalTable } from '../components/tables/IntervalTable'
import { useApi } from '../hooks/useApi'
import { useFilters } from '../hooks/useFilters'
import { periodBoundsUtc, toAnalysisParams, type Filters } from '../lib/filters'
import { formatDateRange } from '../lib/format'
import { api } from '../services/api'
import type { MetaResponse } from '../types/api'

const HOUR = 3_600_000

export default function Dashboard() {
  const meta = useApi((signal) => api.meta(signal), 'meta')
  const { filters, defaults, apply, reset, at, select } = useFilters(meta.data)
  const m = meta.data

  return (
    <AppShell
      header={
        <Header
          loading={meta.loading && !m}
          unavailable={!!meta.error && !m}
          dataSource={m?.data_source}
          periodLabel={filters ? formatDateRange(filters.start, filters.end) : undefined}
        />
      }
    >
      {meta.error && !m ? (
        <Card>
          <ErrorState message={meta.error.userMessage} onRetry={meta.reload} />
        </Card>
      ) : !m || !filters || !defaults ? (
        <LoadingLayout />
      ) : (
        <div className="space-y-6">
          <FilterBar key={JSON.stringify(filters)} meta={m} applied={filters} defaults={defaults} onApply={apply} onReset={reset} />
          <Analysis meta={m} filters={filters} at={at} onSelect={select} />
        </div>
      )}
    </AppShell>
  )
}

interface AnalysisProps {
  meta: MetaResponse
  filters: Filters
  at?: string
  onSelect: (iso: string) => void
}

function Analysis({ meta, filters, at, onSelect }: AnalysisProps) {
  const params = useMemo(() => toAnalysisParams(filters), [filters])
  const key = JSON.stringify(params)
  const overview = useApi((signal) => api.overview(params, signal), key)
  const series = useApi((signal) => api.timeseries(params, signal), key)

  // Keep the selected hour inside the period; otherwise fall back to the first delivery hour.
  const selected = useMemo(() => {
    const [lo, hi] = periodBoundsUtc(filters)
    const t = at ? Date.parse(at) : NaN
    const ok = Number.isFinite(t) && t >= lo && t < hi && t % HOUR === 0
    return new Date(ok ? t : lo).toISOString().replace('.000Z', 'Z')
  }, [at, filters])

  const o = overview.data

  return (
    <>
      {overview.error && !o ? (
        <Card>
          <ErrorState message={overview.error.userMessage} onRetry={overview.reload} />
        </Card>
      ) : (
        <Section
          title="Headline"
          description={o ? `${formatDateRange(o.period.start_date, o.period.end_date)} · cutoff ${o.cutoff.description}` : undefined}
          action={
            o?.data_source.mode === 'DEMO FIXTURE' ? (
              <Badge tone="warn" dot>
                Demo fixture: not live observations
              </Badge>
            ) : undefined
          }
        >
          <KpiCards metrics={o?.metrics} loading={overview.loading} />
        </Section>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <ForecastActualChart
          className="xl:col-span-8"
          data={series.data}
          loading={series.loading}
          error={series.error}
          onRetry={series.reload}
          filters={filters}
          selected={selected}
          onSelect={onSelect}
        />
        <AccuracyPanel className="xl:col-span-4" metrics={o?.metrics} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <IntervalTable key={key} className="xl:col-span-7" params={params} selected={selected} onSelect={onSelect} />
        <SelectedInterval className="xl:col-span-5" params={params} startTimeUtc={selected} />
      </div>

      <DataQualityPanel
        meta={meta}
        metrics={o?.metrics}
        dataSource={o?.data_source}
        coverageDefinition={o?.data_quality.coverage_definition}
      />
    </>
  )
}

function LoadingLayout() {
  return (
    <div className="space-y-6" aria-busy>
      <Skeleton className="h-28 w-full rounded-(--radius-card)" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-32 rounded-(--radius-card)" />
        ))}
      </div>
      <Skeleton className="h-96 w-full rounded-(--radius-card)" />
    </div>
  )
}
