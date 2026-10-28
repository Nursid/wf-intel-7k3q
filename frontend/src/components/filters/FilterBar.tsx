import { ArrowRight, Check, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { DAY_OFFSET_OPTIONS, deliveryDates, rangePresets, sameFilters, validateFilters, type Filters } from '../../lib/filters'
import { formatDateRange } from '../../lib/format'
import type { MetaResponse } from '../../types/api'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Field, Input, Select } from '../ui/Field'
import { InfoTip } from '../ui/InfoTip'

interface FilterBarProps {
  meta: MetaResponse
  applied: Filters
  defaults: Filters
  onApply: (f: Filters) => void
  onReset: () => void
}

/** Edits a draft; nothing is fetched until Apply. Remount (via `key`) to resync with applied filters. */
export function FilterBar({ meta, applied, defaults, onApply, onReset }: FilterBarProps) {
  const [draft, setDraft] = useState<Filters>(applied)
  const errors = validateFilters(draft, meta)
  const valid = Object.keys(errors).length === 0
  const dirty = !sameFilters(draft, applied)
  const isDefault = sameFilters(applied, defaults) && !dirty
  const presets = rangePresets(meta)
  const preset = presets.find((p) => p.start === draft.start && p.end === draft.end)
  const offsets = DAY_OFFSET_OPTIONS.filter((o) => o.value <= meta.max_day_offset)
  const set = (patch: Partial<Filters>) => setDraft((d) => ({ ...d, ...patch }))
  const [delFrom, delTo] = deliveryDates(draft)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (valid && dirty) onApply(draft)
  }

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-col gap-4 p-4 xl:flex-row xl:items-start xl:gap-6" aria-label="Analysis filters">
        <div className="flex items-center gap-2 pt-1 text-xs font-semibold tracking-wider text-ink-muted uppercase xl:w-24 xl:pt-7">
          <SlidersHorizontal className="size-4" aria-hidden />
          Filters
        </div>

        <fieldset className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-3">
          <legend className="sr-only">Decision dates</legend>
          <Field label="Decision dates">
            {(id) => (
              <Select
                id={id}
                value={preset?.label ?? 'custom'}
                onChange={(e) => {
                  const p = presets.find((x) => x.label === e.target.value)
                  if (p) set({ start: p.start, end: p.end })
                }}
              >
                {presets.map((p) => (
                  <option key={p.label} value={p.label}>
                    {p.label}
                  </option>
                ))}
                <option value="custom" disabled>
                  Custom
                </option>
              </Select>
            )}
          </Field>
          <Field label="Decided from" error={errors.start}>
            {(id, d) => (
              <Input
                id={id}
                aria-describedby={d}
                aria-invalid={!!errors.start}
                type="date"
                min={meta.decision_start_date}
                max={meta.decision_end_date}
                value={draft.start}
                required
                onChange={(e) => set({ start: e.target.value })}
              />
            )}
          </Field>
          <Field label="Decided to" error={errors.end}>
            {(id, d) => (
              <Input
                id={id}
                aria-describedby={d}
                aria-invalid={!!errors.end}
                type="date"
                min={meta.decision_start_date}
                max={meta.decision_end_date}
                value={draft.end}
                required
                onChange={(e) => set({ end: e.target.value })}
              />
            )}
          </Field>
          <p className="flex items-center gap-1.5 text-xs text-ink-muted sm:col-span-3">
            <ArrowRight className="size-3.5 text-ink-subtle" aria-hidden />
            Covers deliveries on <strong className="font-medium text-ink">{valid || !errors.start ? formatDateRange(delFrom, delTo) : '—'}</strong>
          </p>
        </fieldset>

        <div aria-hidden className="hidden w-px self-stretch bg-border xl:block" />

        <fieldset className="flex flex-1 flex-col gap-3">
          <legend className="sr-only">Decision cutoff</legend>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(12rem,1fr)_minmax(7rem,9rem)]">
            <Field label="Buying for delivery">
              {(id) => (
                <Select id={id} value={draft.offset} onChange={(e) => set({ offset: Number(e.target.value) })}>
                  {offsets.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Decision time (UK)" error={errors.time}>
              {(id, d) => (
                <Input
                  id={id}
                  aria-describedby={d}
                  type="time"
                  step={60}
                  value={draft.time}
                  required
                  onChange={(e) => set({ time: e.target.value })}
                />
              )}
            </Field>
          </div>
          <p className="flex items-start gap-1.5 text-xs text-ink-subtle">
            <span>
              Each delivery hour uses the latest forecast published by {draft.time || '--:--'} on{' '}
              {offsets.find((o) => o.value === draft.offset)?.phrase ?? `D-${draft.offset}`}, and never one published after
              the hour began.
            </span>
            <InfoTip>
              The default ({meta.default_cutoff.description}) is a pilot assumption, not a market deadline. Confirm it against
              the day-ahead auction the team uses.
            </InfoTip>
          </p>
        </fieldset>

        <div className="flex gap-2 xl:flex-col xl:pt-6">
          <Button type="submit" variant="primary" disabled={!valid || !dirty} icon={<Check className="size-4" aria-hidden />}>
            Apply
          </Button>
          <Button
            variant="ghost"
            disabled={isDefault}
            onClick={() => {
              setDraft(defaults)
              onReset()
            }}
            icon={<RotateCcw className="size-4" aria-hidden />}
          >
            Reset filters
          </Button>
        </div>
      </form>
    </Card>
  )
}
