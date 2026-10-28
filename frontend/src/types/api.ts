// Mirrors backend/app/schemas/analysis.py. All timestamps are ISO 8601 UTC strings ("...Z").

export type IsoUtc = string
export type IsoDate = string // yyyy-mm-dd (Europe/London calendar day)

export type IntervalStatus = 'MATCHED' | 'MISSING_FORECAST' | 'MISSING_ACTUAL' | 'MISSING_BOTH'

export interface DataSourceInfo {
  mode: 'LIVE' | 'DEMO FIXTURE'
  provider: string
  cache_status: 'memory' | 'disk' | 'network' | 'stale-disk' | 'fixture' | null
  stale: boolean
  fetched_at_utc: IsoUtc
  last_successful_fetch_utc: IsoUtc | null
  errors: string[]
}

export interface CutoffPolicy {
  day_offset: number // decide this many days before delivery (1 = day-ahead)
  local_time: string // HH:MM Europe/London
  timezone: string
  description: string
}

/** Scope is set by decision dates; delivery dates follow (decision + day_offset). */
export interface Period {
  decision_start_date: IsoDate
  decision_end_date: IsoDate
  delivery_start_date: IsoDate
  delivery_end_date: IsoDate
  start_utc: IsoUtc // start of first delivery day
  end_utc: IsoUtc // exclusive end of last delivery day
}

export interface Metrics {
  mae_mw: number | null
  rmse_mw: number | null
  mbe_mw: number | null
  wape_pct: number | null
  matched_count: number
  missing_forecast_count: number
  missing_actual_count: number
  missing_both_count: number
  expected_count: number
  coverage_pct: number | null
  mean_forecast_mw: number | null
  mean_actual_mw: number | null
  max_abs_error_mw: number | null
}

/** Empirical spread of error = forecast − actual over matched hours (in-sample, not a probabilistic forecast). */
export interface ErrorDistribution {
  n: number
  percentiles_mw: Record<'p05' | 'p10' | 'p25' | 'p50' | 'p75' | 'p90' | 'p95', number>
  /** Actual minus forecast bounds covering `coverage_pct` % of hours. */
  actual_ranges: { coverage_pct: number; low_mw: number; high_mw: number }[]
  within: { threshold_mw: number; pct: number }[]
  over_forecast_pct: number
  histogram: { low_mw: number; high_mw: number; count: number }[]
  bin_width_mw: number
}

export interface DatasetInfo {
  actual_rows: number
  forecast_rows: number
  forecast_publications: number
  settlement_from: string
  settlement_to: string
  publish_from_utc: string
  publish_to_utc: string
  normalization: Record<string, Record<string, number>>
}

export interface MetaResponse {
  product: string
  decision_start_date: IsoDate
  decision_end_date: IsoDate
  max_day_offset: number
  default_cutoff: CutoffPolicy
  analysis_resolution_minutes: number
  actual_resolution_minutes: number
  dataset: DatasetInfo
  data_source: DataSourceInfo
  assumptions: string[]
}

export interface DataQuality {
  coverage_definition: string
  analysis_resolution_minutes: number
  actual_resolution_minutes: number
  normalization: Record<string, Record<string, number>>
}

export interface OverviewResponse {
  period: Period
  cutoff: CutoffPolicy
  metrics: Metrics
  error_distribution: ErrorDistribution | null
  data_quality: DataQuality
  data_source: DataSourceInfo
}

export interface TimeseriesPoint {
  start_time_utc: IsoUtc
  cutoff_utc: IsoUtc
  forecast_mw: number | null
  publish_time_utc: IsoUtc | null
  actual_mw: number | null
  error_mw: number | null
  status: IntervalStatus
  range_low_mw: number | null // central 80 % range for actual around the forecast
  range_high_mw: number | null
}

export interface ActualPoint {
  start_time_utc: IsoUtc
  actual_mw: number
}

export interface TimeseriesResponse {
  period: Period
  cutoff: CutoffPolicy
  intervals: TimeseriesPoint[]
  actuals_half_hourly: ActualPoint[]
  data_source: DataSourceInfo
}

export interface IntervalRow {
  start_time_utc: IsoUtc
  cutoff_utc: IsoUtc
  publish_time_utc: IsoUtc | null
  forecast_mw: number | null
  actual_mw: number | null
  error_mw: number | null
  abs_error_mw: number | null
  status: IntervalStatus
  eligible_versions: number
  total_versions: number
  lead_time_minutes: number | null
  horizon_minutes: number | null
}

export type SortColumn =
  | 'start_time_utc'
  | 'publish_time_utc'
  | 'forecast_mw'
  | 'actual_mw'
  | 'error_mw'
  | 'abs_error_mw'
  | 'status'
export type SortDir = 'asc' | 'desc'

export interface IntervalsResponse {
  period: Period
  cutoff: CutoffPolicy
  items: IntervalRow[]
  page: number
  page_size: number
  total: number
  total_pages: number
  sort_by: SortColumn
  sort_dir: SortDir
  data_source: DataSourceInfo
}

export interface ForecastVersion {
  publish_time_utc: IsoUtc
  forecast_mw: number
  eligible: boolean
  selected: boolean
  ineligible_reason: 'AFTER_CUTOFF' | 'AFTER_DELIVERY_START' | null
  minutes_before_cutoff: number
  horizon_minutes: number
}

export interface ForecastHistoryResponse {
  start_time_utc: IsoUtc
  cutoff_utc: IsoUtc
  cutoff: CutoffPolicy
  actual_mw: number | null
  selected: ForecastVersion | null
  eligible_versions: number
  total_versions: number
  versions: ForecastVersion[]
  data_source: DataSourceInfo
}

export interface HealthResponse {
  status: 'ok'
  version: string
  data_mode: 'live' | 'fixture'
  dataset_loaded: boolean
  cache_fetched_at_utc: IsoUtc | null
}

/** Query parameters shared by all /api/analysis/* endpoints. */
export interface AnalysisParams {
  decision_start_date: IsoDate
  decision_end_date: IsoDate
  cutoff_day_offset: number
  cutoff_time: string // HH:MM Europe/London
}
