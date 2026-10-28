import { Info } from 'lucide-react'
import type { ReactNode } from 'react'
import { useId } from 'react'
import { cn } from '../../lib/cn'

/** Small "i" icon with an accessible tooltip, shown on hover and keyboard focus. */
export function InfoTip({ children, label = 'More information', className }: { children: ReactNode; label?: string; className?: string }) {
  const id = useId()
  return (
    <span className={cn('group relative inline-flex align-middle', className)}>
      <button
        type="button"
        aria-label={label}
        aria-describedby={id}
        className="rounded text-ink-subtle hover:text-ink-muted focus-visible:text-ink-muted"
      >
        <Info className="size-3.5" aria-hidden />
      </button>
      <span
        role="tooltip"
        id={id}
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-20 mb-2 w-64 -translate-x-1/2 rounded-lg bg-ink px-3 py-2 text-xs leading-relaxed font-normal text-white opacity-0 shadow-lg transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100"
      >
        {children}
      </span>
    </span>
  )
}
