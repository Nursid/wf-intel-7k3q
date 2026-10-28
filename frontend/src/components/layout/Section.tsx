import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface SectionProps {
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
  children: ReactNode
}

export function Section({ title, description, action, className, children }: SectionProps) {
  return (
    <section className={cn('space-y-3', className)} aria-label={title}>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-xs font-semibold tracking-wider text-ink-muted uppercase">{title}</h2>
          {description && <p className="mt-1 text-xs text-ink-subtle">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}
