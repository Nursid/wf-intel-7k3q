import { Check, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { cn } from '../../lib/cn'
import { DAY_OFFSET_OPTIONS, rangePresets, sameFilters, validateFilters, type Filters } from '../../lib/filters'
import type { CutoffMode, MetaResponse } from '../../types/api'
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
  const set = (patch: Partial<Filters>) => setDraft((d) => ({ ...d, ...patch }))

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
          <legend className="sr-only">Delivery period</legend>
          <Field label="Quick range">
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
          <Field label="Delivery from" error={errors.start}>
            {(id, d) => (
              <Input
                id={id}
                aria-describedby={d}
                aria-invalid={!!errors.start}
                type="date"
                min={meta.available_start_date}
                max={meta.available_end_date}
                value={draft.start}
                required
                onChange={(e) => set({ start: e.target.value })}
              />
            )}
          </Field>
          <Field label="Delivery to" error={errors.end}>
            {(id, d) => (
              <Input
                id={id}
                aria-describedby={d}
                aria-invalid={!!errors.end}
                type="date"
                min={meta.available_start_date}
                max={meta.available_end_date}
                value={draft.end}
                required
                onChange={(e) => set({ end: e.target.value })}
              />
            )}
          </Field>
        </fieldset>

        <div aria-hidden className="hidden w-px self-stretch bg-border xl:block" />

        <fieldset className="flex flex-1 flex-col gap-3">
          <legend className="sr-only">Decision cutoff</legend>
          <div className="flex items-center gap-1.5 text-xs font-medium text-ink-muted">
            Decision cutoff (Europe/London)
            <InfoTip>
              Only forecasts published at or before this moment are used. The default ({meta.default_cutoff.description}) is
              a pilot assumption, not a market deadline.
            </InfoTip>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[auto_minmax(11.5rem,1fr)_minmax(7rem,9rem)]">
            <ModeToggle value={draft.mode} onChange={(mode) => set({ mode })} />
            {draft.mode === 'relative' ? (
              <>
                <Field label="Decision day" className="[&>label]:sr-only">
                  {(id) => (
                    <Select id={id} value={draft.offset} onChange={(e) => set({ offset: Number(e.target.value) })}>
                      {DAY_OFFSET_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label="Decision time" className="[&>label]:sr-only" error={errors.time}>
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
              </>
            ) : (
              <Field label="Decision date and time" className="sm:col-span-2 [&>label]:sr-only" error={errors.decision}>
                {(id, d) => (
                  <Input
                    id={id}
                    aria-describedby={d}
                    type="datetime-local"
                    value={draft.decision}
                    required
                    onChange={(e) => set({ decision: e.target.value })}
                  />
                )}
              </Field>
            )}
          </div>
          <p className="text-xs text-ink-subtle">
            {draft.mode === 'relative'
              ? `Each delivery hour uses the latest forecast published by ${draft.time || '--:--'} on ${
                  DAY_OFFSET_OPTIONS.find((o) => o.value === draft.offset)?.phrase ?? `D-${draft.offset}`
                } (Europe/London).`
              : 'One fixed decision moment applies to every delivery hour in the period.'}
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

function ModeToggle({ value, onChange }: { value: CutoffMode; onChange: (m: CutoffMode) => void }) {
  const options: { v: CutoffMode; label: string }[] = [
    { v: 'relative', label: 'Day-ahead rule' },
    { v: 'absolute', label: 'Fixed time' },
  ]
  return (
    <div role="radiogroup" aria-label="Cutoff type" className="inline-flex h-9 rounded-lg bg-surface-muted p-0.5 ring-1 ring-border ring-inset">
      {options.map((o) => (
        <button
          key={o.v}
          type="button"
          role="radio"
          aria-checked={value === o.v}
          onClick={() => onChange(o.v)}
          className={cn(
            'rounded-md px-3 text-xs font-medium whitespace-nowrap transition-colors',
            value === o.v ? 'bg-surface text-ink shadow-sm ring-1 ring-border' : 'text-ink-muted hover:text-ink',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
