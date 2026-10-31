import { useState } from 'react'
import type { ReactNode } from 'react'
import { useLanguage } from '../lib/i18n'
import { Icon } from './Icon'
import { ReviewLink } from './ReviewLink'

const SIDEBAR_KEY = 'ai-change-inspector.sidebar-collapsed'

export function AppShell({ path, navigate, children }: { path: string; navigate: (path: string) => void; children: ReactNode }) {
  const { t, language, setLanguage } = useLanguage()
  const [hiddenTooltip, setHiddenTooltip] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(SIDEBAR_KEY) === 'true' } catch { return false }
  })
  function toggle() {
    const next = !collapsed
    setCollapsed(next)
    try { localStorage.setItem(SIDEBAR_KEY, String(next)) } catch { /* Session preference still works. */ }
  }
  const reviews = path.startsWith('/reviews')
  const section = path === '/' ? t('overview') : path.includes('/compare/') ? t('comparisonTitle') : path.endsWith('/evolution') ? t('evolutionTitle') : /^\/reviews\/.+/.test(path) ? t('detail') : reviews ? t('inbox') : t('manual')
  const reviewId = /^\/reviews\/([0-9a-f-]{36})(?:\/|$)/.exec(path)?.[1]
  return <div className={`app-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
    <a className="skip-link" href="#workspace">{t('skipContent')}</a>
    <div className="sidebar">
      <div className="sidebar-header">
        <a className="brand" href="/" aria-label="AI Change Inspector" onClick={(event) => {
          if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); navigate('/') }
        }}><svg className="brand-logo" viewBox="0 0 36 42" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M18 2 32 7v12c0 10-6 16-14 21C10 35 4 29 4 19V7Z" /><path d="m14 14-5 5 5 5m8-10 5 5-5 5" /></svg><span className="brand-name">AI Change<span>Inspector</span></span></a>
        <button type="button" className="sidebar-toggle" aria-label={t(collapsed ? 'expandSidebar' : 'collapseSidebar')} aria-expanded={!collapsed} aria-controls="sidebar-links" onClick={toggle}>
          <Icon name={collapsed ? 'open' : 'close'} />
        </button>
      </div>
      <nav id="sidebar-links" aria-label={t('navigation')}>
        {([{ href: '/', label: t('overview'), icon: 'overview', active: path === '/' }, { href: '/reviews', label: t('inbox'), icon: 'inbox', active: reviews }, { href: '/diff', label: t('manual'), icon: 'diff', active: path === '/diff' }] as const).map((item) =>
          <a key={item.href} href={item.href} className={`sidebar-link${item.active ? ' is-active' : ''}`} aria-current={item.active ? 'page' : undefined} aria-label={item.label}
            aria-describedby={`nav-tip-${item.icon}`} data-tooltip-hidden={hiddenTooltip === item.href}
            onFocus={() => setHiddenTooltip(null)} onMouseEnter={() => setHiddenTooltip(null)}
            onKeyDown={(event) => { if (event.key === 'Escape') setHiddenTooltip(item.href) }} onClick={(event) => {
            if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); navigate(item.href) }
          }}><Icon name={item.icon} /><span className="nav-label">{item.label}</span><span id={`nav-tip-${item.icon}`} className="nav-tooltip" role="tooltip">{item.label}</span></a>)}
      </nav>
      {reviewId && <nav className="sidebar-context" aria-label={t('relatedReviews')}><span className="context-label">{t('reviewLabel')} · {reviewId.slice(0, 8)}</span>
        <ReviewLink href={`/reviews/${reviewId}`} navigate={navigate} variant="text" current={path === `/reviews/${reviewId}`}><Icon name="file" />{t('detail')}</ReviewLink>
        <ReviewLink href={`/reviews/${reviewId}/evolution`} navigate={navigate} variant="text" current={path.endsWith('/evolution')}><Icon name="history" />{t('evolutionTitle')}</ReviewLink>
      </nav>}
      <div className="sidebar-footer"><span className="local-dot" aria-hidden="true" /><span className="nav-label">{t('localWorkspace')}</span></div>
    </div>
    <div className="workspace" id="workspace" tabIndex={-1}>
      <header className="topbar"><span className="topbar-section"><span className="workspace-label">{t('workspace')} / </span>{section}</span><span className="topbar-note">{t('badge')}</span>
        <label className="language-control"><span className="sr-only">{t('language')}</span>
          <select value={language} onChange={(event) => setLanguage(event.target.value === 'es' ? 'es' : 'en')}>
            <option value="en" lang="en">EN</option><option value="es" lang="es">ES</option>
          </select>
        </label>
      </header>
      {children}
    </div>
  </div>
}
