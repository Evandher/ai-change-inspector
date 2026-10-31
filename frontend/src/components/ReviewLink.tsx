import type { ReactNode } from 'react'

export function ReviewLink({ href, navigate, children, current = false, variant = 'action', ariaLabel }: { href: string; navigate: (path: string) => void; children: ReactNode; current?: boolean; variant?: 'action' | 'text' | 'quiet'; ariaLabel?: string }) {
  return <a href={href} aria-label={ariaLabel} aria-current={current ? 'page' : undefined} className={variant === 'text' ? 'review-reference break-all' : `navigation-action${variant === 'quiet' ? ' quiet' : ''}`} onClick={(event) => {
    if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); navigate(href)
    }
  }}>{children}</a>
}
