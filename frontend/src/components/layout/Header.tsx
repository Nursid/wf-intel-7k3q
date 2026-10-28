import { CalendarRange, Database, RefreshCw, Wind } from 'lucide-react'
import type { ReactNode } from 'react'
import type { DataSourceInfo } from '../../types/api'
import { formatLocal, formatRelative } from '../../lib/format'
import { Badge } from '../ui/Badge'
import { Skeleton } from '../ui/States'

interface HeaderProps {
  periodLabel?: string
  dataSource?: DataSourceInfo
  loading: boolean
  unavailable: boolean
}

export function Header({ periodLabel, dataSource, loading, unavailable }: HeaderProps) {
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 py-4 md:px-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-brand text-white">
            <Wind className="size-5" aria-hidden />
          </div>
          <div>
            <h1 className="text-xl leading-7 font-semibold tracking-tight">Wind Forecast Intelligence</h1>
            <p className="text-xs text-ink-muted">UK National Wind Generation</p>
          </div>
        </div>

        <dl className="flex flex-wrap items-center gap-x-6 gap-y-3 text-xs">
          <HeaderItem icon={<CalendarRange className="size-4" aria-hidden />} label="Analysis period">
            {loading ? <Skeleton className="h-4 w-36" /> : (periodLabel ?? '—')}
          </HeaderItem>

          <HeaderItem icon={<Database className="size-4" aria-hidden />} label="Data source">
            <span className="flex items-center gap-2">
              Elexon BMRS
              {loading ? (
                <Skeleton className="h-5 w-12 rounded-full" />
              ) : unavailable || !dataSource ? (
                <Badge tone="danger" dot>
                  Unavailable
                </Badge>
              ) : (
                <SourceBadges ds={dataSource} />
              )}
            </span>
          </HeaderItem>

          <HeaderItem icon={<RefreshCw className="size-4" aria-hidden />} label="Last successful fetch">
            {loading ? (
              <Skeleton className="h-4 w-40" />
            ) : dataSource?.last_successful_fetch_utc ? (
              <time dateTime={dataSource.last_successful_fetch_utc} title={formatRelative(dataSource.last_successful_fetch_utc)}>
                {formatLocal(dataSource.last_successful_fetch_utc)}
              </time>
            ) : (
              '—'
            )}
          </HeaderItem>
        </dl>
      </div>
    </header>
  )
}

function SourceBadges({ ds }: { ds: DataSourceInfo }) {
  return (
    <>
      {ds.mode === 'LIVE' ? (
        <Badge tone="ok" dot title="Values come from the Elexon API (cached locally)">
          LIVE
        </Badge>
      ) : (
        <Badge tone="warn" dot title="Bundled sample for offline development. Not a live observation.">
          DEMO FIXTURE
        </Badge>
      )}
      {ds.stale && (
        <Badge tone="warn" title={ds.errors.join('; ')}>
          Stale cache
        </Badge>
      )}
    </>
  )
}

function HeaderItem({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="text-ink-subtle">{icon}</span>
      <div>
        <dt className="text-[11px] text-ink-subtle">{label}</dt>
        <dd className="font-medium text-ink">{children}</dd>
      </div>
    </div>
  )
}
