import { useId, useState } from 'react'
import type { ReactNode } from 'react'

/** CSS owns the transition; content stays mounted and rapid toggles need no timers. */
export function AnimatedDisclosure({ label, defaultOpen = false, children }: { label: string; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  const contentId = useId()
  return <div className="finding-body" data-open={open}>
    <button type="button" className="disclosure-toggle" aria-expanded={open} aria-controls={contentId} onClick={() => setOpen((value) => !value)}>
      <span className="disclosure-chevron" aria-hidden="true">›</span>{label}
    </button>
    <div className="disclosure-content" id={contentId} aria-hidden={!open} inert={!open}>
      <div className="disclosure-inner">{children}</div>
    </div>
  </div>
}
