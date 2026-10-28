import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { defaultFilters, filtersFromSearch, filtersToSearch, type Filters } from '../lib/filters'
import type { MetaResponse } from '../types/api'

/** Applied filters live in the URL so views are shareable and survive reloads. */
export function useFilters(meta: MetaResponse | undefined) {
  const [sp, setSp] = useSearchParams()
  const defaults = useMemo(() => (meta ? defaultFilters(meta) : undefined), [meta])
  const filters = useMemo(
    () => (defaults && meta ? filtersFromSearch(sp, defaults, meta.max_day_offset) : undefined),
    [sp, defaults, meta],
  )
  const at = sp.get('at') ?? undefined

  const apply = useCallback(
    (f: Filters) => {
      if (!defaults) return
      setSp(filtersToSearch(f, defaults), { replace: false })
    },
    [defaults, setSp],
  )

  const reset = useCallback(() => setSp(new URLSearchParams()), [setSp])

  /** Selected delivery interval (UTC ISO), kept alongside the filters. */
  const select = useCallback(
    (iso: string) =>
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('at', iso)
          return next
        },
        { replace: true },
      ),
    [setSp],
  )

  return { filters, defaults, apply, reset, at, select }
}
