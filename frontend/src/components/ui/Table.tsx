import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import type { HTMLAttributes, ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

/** `scroll={false}` when a parent already scrolls; a nested scroller would break the sticky header. */
export function Table({ className, scroll = true, children }: { className?: string; scroll?: boolean; children: ReactNode }) {
  return (
    <div className={cn(scroll && 'overflow-x-auto', className)}>
      <table className="w-full border-collapse text-left text-sm">{children}</table>
    </div>
  )
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="sticky top-0 z-10 bg-surface-muted text-xs font-medium text-ink-muted">{children}</thead>
  )
}

interface ThProps extends ThHTMLAttributes<HTMLTableCellElement> {
  align?: 'left' | 'right'
  sort?: 'asc' | 'desc' | null
  onSort?: () => void
}

export function Th({ align = 'left', sort, onSort, className, children, ...props }: ThProps) {
  const ariaSort = sort === 'asc' ? 'ascending' : sort === 'desc' ? 'descending' : onSort ? 'none' : undefined
  const content = onSort ? (
    <button
      type="button"
      onClick={onSort}
      className={cn('inline-flex items-center gap-1 rounded hover:text-ink', align === 'right' && 'flex-row-reverse')}
    >
      {children}
      {sort === 'asc' ? (
        <ArrowUp className="size-3" aria-hidden />
      ) : sort === 'desc' ? (
        <ArrowDown className="size-3" aria-hidden />
      ) : (
        <ArrowUpDown className="size-3 opacity-40" aria-hidden />
      )}
    </button>
  ) : (
    children
  )
  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={cn(
        'border-b border-border px-4 py-2.5 font-medium whitespace-nowrap',
        align === 'right' && 'text-right',
        className,
      )}
      {...props}
    >
      {content}
    </th>
  )
}

export function Tr({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn('border-b border-border last:border-0', className)} {...props} />
}

export function Td({ align = 'left', className, ...props }: TdHTMLAttributes<HTMLTableCellElement> & { align?: 'left' | 'right' }) {
  return (
    <td
      className={cn('px-4 py-2.5 whitespace-nowrap', align === 'right' && 'text-right tabular', className)}
      {...props}
    />
  )
}
