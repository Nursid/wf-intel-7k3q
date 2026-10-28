import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export type BadgeTone = 'neutral' | 'forecast' | 'actual' | 'ok' | 'warn' | 'danger' | 'over' | 'under'

const tones: Record<BadgeTone, string> = {
  neutral: 'bg-surface-muted text-ink-muted ring-border',
  forecast: 'bg-forecast-soft text-forecast ring-forecast/20',
  actual: 'bg-actual-soft text-actual ring-actual/20',
  ok: 'bg-ok-soft text-ok ring-ok/20',
  warn: 'bg-warn-soft text-warn ring-warn/25',
  danger: 'bg-danger-soft text-danger ring-danger/20',
  over: 'bg-over-soft text-over ring-over/25',
  under: 'bg-under-soft text-under ring-under/20',
}

interface BadgeProps {
  tone?: BadgeTone
  dot?: boolean
  icon?: ReactNode
  children: ReactNode
  className?: string
  title?: string
}

export function Badge({ tone = 'neutral', dot, icon, children, className, title }: BadgeProps) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset',
        tones[tone],
        className,
      )}
    >
      {dot && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
      {icon}
      {children}
    </span>
  )
}
