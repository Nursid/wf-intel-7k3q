import { ChevronLeft, ChevronRight, Table2 } from 'lucide-react'
import { useState } from 'react'
import { useApi } from '../../hooks/useApi'
import { cn } from '../../lib/cn'
import { formatInt, formatLocalShort, formatMW, formatSignedMW, formatUtc } from '../../lib/format'
import { api } from '../../services/api'
import type { AnalysisParams, IntervalStatus, SortColumn, SortDir } from '../../types/api'
import { Badge, type BadgeTone } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card, CardHeader } from '../ui/Card'
import { Select } from '../ui/Field'
import { EmptyState, ErrorState, Skeleton } from '../ui/States'
import { Table, Td, Th, THead, Tr } from '../ui/Table'

const STATUS: Record<IntervalStatus, { tone: BadgeTone; label: string }> = {
  MATCHED: { tone: 'ok', label: 'Matched' },
  MISSING_FORECAST: { tone: 'warn', label: 'No forecast' },
  MISSING_ACTUAL: { tone: 'warn', label: 'No actual' },
  MISSING_BOTH: { tone: 'danger', label: 'No data' },
}

const COLUMNS: { key: SortColumn; label: string; align?: 'right'; firstDir: SortDir }[] = [
  { key: 'start_time_utc', label: 'Delivery hour', firstDir: 'asc' },
  { key: 'publish_time_utc', label: 'Published', firstDir: 'desc' },
  { key: 'forecast_mw', label: 'Forecast', align: 'right', firstDir: 'desc' },
  { key: 'actual_mw', label: 'Actual', align: 'right', firstDir: 'desc' },
  { key: 'error_mw', label: 'Error', align: 'right', firstDir: 'desc' },
  { key: 'abs_error_mw', label: '|Error|', align: 'right', firstDir: 'desc' },
  { key: 'status', label: 'Status', firstDir: 'asc' },
]

const PAGE_SIZES = [24, 48, 96]

interface Props {
  params: AnalysisParams
  selected?: string
  onSelect: (iso: string) => void
  className?: string
}

/** Server-side sorted and paginated. Remount (via `key`) when filters change to reset paging. */
export function IntervalTable({ params, selected, onSelect, className }: Props) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(24)
  const [sortBy, setSortBy] = useState<SortColumn>('start_time_utc')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const q = useApi(
    (signal) => api.intervals(params, { page, pageSize, sortBy, sortDir }, signal),
    JSON.stringify([params, page, pageSize, sortBy, sortDir]),
  )
  const d = q.data

  const sort = (col: (typeof COLUMNS)[number]) => {
    if (col.key === sortBy) setSortDir((s) => (s === 'asc' ? 'desc' : 'asc'))
    else {
      setSortBy(col.key)
      setSortDir(col.firstDir)
    }
    setPage(1)
  }

  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader
        icon={<Table2 className="size-4" />}
        title="Interval analysis"
        subtitle="Times in Europe/London. Hover a delivery hour for UTC. Click a row to inspect its forecast history."
      />
      {/* On wide screens the table fills the card height set by its neighbour and scrolls inside it. */}
      <div className="mt-4 xl:relative xl:min-h-[420px] xl:flex-1">
        {q.error && !d ? (
          <ErrorState message={q.error.userMessage} onRetry={q.reload} />
        ) : !d ? (
          <div className="space-y-2 px-5 pb-5">
            {Array.from({ length: 8 }, (_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : d.total === 0 ? (
          <EmptyState title="No intervals" description="The selected period contains no delivery hours." />
        ) : (
          <div className={cn('max-h-[560px] overflow-auto border-y border-border transition-opacity xl:absolute xl:inset-0 xl:max-h-none', q.loading && 'opacity-60')}>
            <Table scroll={false}>
              <THead>
                <tr>
                  {COLUMNS.map((c) => (
                    <Th key={c.key} align={c.align} sort={sortBy === c.key ? sortDir : null} onSort={() => sort(c)}>
                      <span>
                        {c.label}
                        {c.align === 'right' && <span className="font-normal text-ink-subtle"> MW</span>}
                      </span>
                    </Th>
                  ))}
                </tr>
              </THead>
              <tbody>
                {d.items.map((r) => {
                  const isSel = r.start_time_utc === selected
                  const s = STATUS[r.status]
                  return (
                    <Tr
                      key={r.start_time_utc}
                      onClick={() => onSelect(r.start_time_utc)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          onSelect(r.start_time_utc)
                        }
                      }}
                      tabIndex={0}
                      aria-selected={isSel}
                      className={cn(
                        'cursor-pointer hover:bg-surface-muted focus-visible:bg-forecast-soft',
                        isSel && 'bg-forecast-soft hover:bg-forecast-soft',
                      )}
                    >
                      <Td className="font-medium tabular" title={formatUtc(r.start_time_utc)}>
                        {isSel && <span aria-hidden className="mr-2 inline-block size-1.5 rounded-full bg-forecast align-middle" />}
                        {formatLocalShort(r.start_time_utc)}
                      </Td>
                      <Td className="text-ink-muted tabular" title={r.publish_time_utc ? formatUtc(r.publish_time_utc) : undefined}>
                        {formatLocalShort(r.publish_time_utc)}
                      </Td>
                      <Td align="right">{formatMW(r.forecast_mw, false)}</Td>
                      <Td align="right">{formatMW(r.actual_mw, false)}</Td>
                      <Td
                        align="right"
                        className={r.error_mw === null ? '' : r.error_mw > 0 ? 'text-over' : r.error_mw < 0 ? 'text-under' : ''}
                      >
                        {formatSignedMW(r.error_mw, false)}
                      </Td>
                      <Td align="right">{formatMW(r.abs_error_mw, false)}</Td>
                      <Td>
                        <Badge tone={s.tone} dot>
                          {s.label}
                        </Badge>
                      </Td>
                    </Tr>
                  )
                })}
              </tbody>
            </Table>
          </div>
        )}
      </div>

      {d && d.total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-xs text-ink-muted">
          <span className="tabular">
            {formatInt((d.page - 1) * d.page_size + 1)}–{formatInt(Math.min(d.page * d.page_size, d.total))} of {formatInt(d.total)} hours
          </span>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2">
              Rows
              <Select
                className="h-8 w-20 text-xs"
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value))
                  setPage(1)
                }}
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </label>
            <Button
              size="sm"
              aria-label="Previous page"
              disabled={d.page <= 1}
              onClick={() => setPage((p) => p - 1)}
              icon={<ChevronLeft className="size-4" aria-hidden />}
            />
            <span className="tabular">
              Page {d.page} / {d.total_pages}
            </span>
            <Button
              size="sm"
              aria-label="Next page"
              disabled={d.page >= d.total_pages}
              onClick={() => setPage((p) => p + 1)}
              icon={<ChevronRight className="size-4" aria-hidden />}
            />
          </div>
        </div>
      )}
    </Card>
  )
}
