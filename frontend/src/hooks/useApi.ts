import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../services/api'

export interface ApiState<T> {
  /** Latest successful response; kept while a newer request is loading. */
  data: T | undefined
  error: ApiError | undefined
  loading: boolean
  reload: () => void
}

interface Settled<T> {
  requestKey: string
  data: T | undefined
  error: ApiError | undefined
}

/**
 * Runs `fetcher` whenever `key` changes; aborts superseded requests so stale responses never win.
 * `key` should serialise every input the fetcher depends on.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, key: string): ApiState<T> {
  const [nonce, setNonce] = useState(0)
  const [settled, setSettled] = useState<Settled<T>>({ requestKey: '', data: undefined, error: undefined })
  const fetcherRef = useRef(fetcher)
  const requestKey = `${key}#${nonce}`

  useEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    const ctrl = new AbortController()
    fetcherRef
      .current(ctrl.signal)
      .then((data) => {
        if (!ctrl.signal.aborted) setSettled({ requestKey, data, error: undefined })
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        const error = err instanceof ApiError ? err : new ApiError(0, 'UNKNOWN', String(err))
        setSettled((prev) => ({ requestKey, data: prev.data, error }))
      })
    return () => ctrl.abort()
  }, [requestKey])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  const current = settled.requestKey === requestKey
  return { data: settled.data, error: current ? settled.error : undefined, loading: !current, reload }
}
