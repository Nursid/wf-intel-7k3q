import type { ReactNode } from 'react'

export function AppShell({ header, children }: { header: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      {header}
      <main className="mx-auto w-full max-w-[1440px] px-4 py-6 md:px-6">{children}</main>
      <footer className="mx-auto w-full max-w-[1440px] px-4 pb-8 text-xs text-ink-subtle md:px-6">
        Source: Elexon BMRS Insights API: national wind outturn (FUELHH, fuel type WIND) and wind generation forecast
        (WINDFOR). Times are shown in Europe/London (GMT/BST) unless marked UTC. Historical forecast analysis only. This
        tool does not recommend purchase volumes.
      </footer>
    </div>
  )
}
