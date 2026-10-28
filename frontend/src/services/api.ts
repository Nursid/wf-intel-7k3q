import type {
  AnalysisParams,
  ForecastHistoryResponse,
  HealthResponse,
  IntervalsResponse,
  MetaResponse,
  OverviewResponse,
  SortColumn,
  SortDir,
  TimeseriesResponse,
} from '../types/api'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }

  /** Short, user-facing explanation. */
  get userMessage(): string {
    if (this.status === 0) return 'Cannot reach the analysis service. Check that the backend is running.'
    if (this.status === 503) return 'Elexon data is temporarily unavailable and no cached copy exists.'
    if (this.status === 422) return this.message
    return `The analysis service returned an error (${this.status}).`
  }
}

type Query = Record<string, string | number | undefined>

function toSearch(params: Query): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, params: Query = {}, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}${toSearch(params)}`, { signal, headers: { Accept: 'application/json' } })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'NETWORK', 'Network request failed')
  }
  if (!res.ok) {
    let code = 'ERROR'
    let message = res.statusText
    try {
      const body = (await res.json()) as { error?: { code: string; message: string } }
      if (body.error) ({ code, message } = body.error)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message)
  }
  return (await res.json()) as T
}

const analysisQuery = (p: AnalysisParams): Query => ({ ...p })

export const api = {
  baseUrl: BASE_URL,
  health: (signal?: AbortSignal) => request<HealthResponse>('/health', {}, signal),
  meta: (signal?: AbortSignal) => request<MetaResponse>('/api/meta', {}, signal),
  overview: (p: AnalysisParams, signal?: AbortSignal) =>
    request<OverviewResponse>('/api/analysis/overview', analysisQuery(p), signal),
  timeseries: (p: AnalysisParams, signal?: AbortSignal) =>
    request<TimeseriesResponse>('/api/analysis/timeseries', analysisQuery(p), signal),
  intervals: (
    p: AnalysisParams,
    opts: { page: number; pageSize: number; sortBy: SortColumn; sortDir: SortDir },
    signal?: AbortSignal,
  ) =>
    request<IntervalsResponse>(
      '/api/analysis/intervals',
      { ...analysisQuery(p), page: opts.page, page_size: opts.pageSize, sort_by: opts.sortBy, sort_dir: opts.sortDir },
      signal,
    ),
  forecastHistory: (p: AnalysisParams, startTimeUtc: string, signal?: AbortSignal) =>
    request<ForecastHistoryResponse>(
      '/api/analysis/forecast-history',
      { ...analysisQuery(p), start_time: startTimeUtc },
      signal,
    ),
}
