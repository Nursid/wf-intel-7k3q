import { AlertTriangle, CheckCircle2, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { formatInt, formatLocal, formatPct, formatUtc } from '../../lib/format'
import type { DataSourceInfo, MetaResponse, Metrics } from '../../types/api'
import { Badge } from '../ui/Badge'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { EmptyState, Skeleton } from '../ui/States'
import { Table, Td, Th, THead, Tr } from '../ui/Table'

const CACHE_LABEL: Record<string, string> = {
  memory: 'Served from memory cache',
  disk: 'Served from local disk cache',
  network: 'Fetched from Elexon on this load',
  'stale-disk': 'Stale cache: latest fetch failed',
  fixture: 'Bundled demo fixture',
}

interface Props {
  meta: MetaResponse
  metrics?: Metrics
  dataSource?: DataSourceInfo
  coverageDefinition?: string
}

export function DataQualityPanel({ meta, metrics, dataSource, coverageDefinition }: Props) {
  const ds = dataSource ?? meta.data_source
  const live = ds.mode === 'LIVE'
  return (
    <Card>
      <CardHeader
        icon={<ShieldCheck className="size-4" />}
        title="Data quality"
        subtitle="Where the numbers come from and what is missing"
        action={
          live ? (
            <Badge tone="ok" dot>
              LIVE · Elexon API
            </Badge>
          ) : (
            <Badge tone="warn" dot>
              DEMO FIXTURE: not live observations
            </Badge>
          )
        }
      />
      <CardBody className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm lg:col-span-5">
          <Item label="Last successful fetch">{formatLocal(ds.last_successful_fetch_utc)}</Item>
          <Item label="Cache">{(ds.cache_status && CACHE_LABEL[ds.cache_status]) ?? '—'}</Item>
          <Item label="API errors">
            {ds.errors.length ? (
              <span className="flex items-start gap-1.5 text-danger">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                {ds.errors.join('; ')}
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-ok">
                <CheckCircle2 className="size-3.5" aria-hidden />
                None
              </span>
            )}
          </Item>
          <Item label="Coverage">
            {metrics ? (
              `${formatPct(metrics.coverage_pct)} (${formatInt(metrics.matched_count)} / ${formatInt(metrics.expected_count)})`
            ) : (
              <Skeleton className="h-4 w-24" />
            )}
          </Item>
          <Item label="Missing forecast">
            {metrics ? <Count n={metrics.missing_forecast_count} unit="hours" /> : <Skeleton className="h-4 w-16" />}
          </Item>
          <Item label="Missing actual">
            {metrics ? <Count n={metrics.missing_actual_count} unit="hours" /> : <Skeleton className="h-4 w-16" />}
          </Item>
          <div className="col-span-2 text-xs leading-relaxed text-ink-muted">
            <span className="font-medium text-ink">Coverage definition.</span>{' '}
            {coverageDefinition ?? 'Matched intervals ÷ expected hourly delivery intervals in the selected period.'}
          </div>
        </dl>

        <div className="space-y-3 lg:col-span-7">
          <p className="text-xs text-ink-muted">
            Downloaded: {formatInt(meta.dataset.forecast_publications)} WINDFOR publications ({formatUtc(meta.dataset.publish_from_utc)} →{' '}
            {formatUtc(meta.dataset.publish_to_utc)}) and FUELHH WIND settlement days {meta.dataset.settlement_from} →{' '}
            {meta.dataset.settlement_to}.
          </p>
          <ValidationTable meta={meta} />
          <details className="group rounded-lg border border-border px-3 py-2 text-xs">
            <summary className="cursor-pointer font-medium text-ink select-none">Assumptions & scope</summary>
            <ul className="mt-2 list-disc space-y-1.5 pl-4 leading-relaxed text-ink-muted">
              {meta.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </details>
        </div>
      </CardBody>
    </Card>
  )
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-ink-subtle">{label}</dt>
      <dd className="mt-0.5 font-medium tabular">{children}</dd>
    </div>
  )
}

function Count({ n, unit }: { n: number; unit: string }) {
  return <span className={n ? 'text-warn' : ''}>{`${formatInt(n)} ${unit}`}</span>
}

const CHECKS: [key: string, label: string][] = [
  ['received', 'Received'],
  ['accepted', 'Accepted'],
  ['invalid', 'Invalid'],
  ['non_wind', 'Non-wind'],
  ['duplicates', 'Duplicates'],
]

function ValidationTable({ meta }: { meta: MetaResponse }) {
  const n = meta.dataset.normalization
  if (!n.actuals && !n.forecasts) {
    return <EmptyState title="No ingest report" description="The demo fixture does not carry validation statistics." />
  }
  const datasets = [
    ['FUELHH (actual)', n.actuals],
    ['WINDFOR (forecast)', n.forecasts],
  ] as const
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <Table>
        <THead>
          <tr>
            <Th>Validation</Th>
            {CHECKS.map(([k, label]) => (
              <Th key={k} align="right">
                {label}
              </Th>
            ))}
          </tr>
        </THead>
        <tbody>
          {datasets.map(([name, rep]) => (
            <Tr key={name}>
              <Td className="font-medium">{name}</Td>
              {CHECKS.map(([k]) => (
                <Td key={k} align="right" className={k !== 'received' && k !== 'accepted' && rep?.[k] ? 'text-warn' : ''}>
                  {formatInt(rep?.[k])}
                </Td>
              ))}
            </Tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
}
