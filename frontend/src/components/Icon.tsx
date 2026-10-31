// Small inline icons keep navigation independent of an external icon package.
export type IconName = 'inbox' | 'diff' | 'close' | 'open' | 'overview' | 'file' | 'history' | 'columns' | 'arrow' | 'info' | 'folder' | 'alert' | 'person'
const paths: Partial<Record<IconName, string>> = {
  overview: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  file: 'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7',
  history: 'M4 11a8 8 0 1 1 2 7M4 5v6h6M12 8v5l3 2',
  columns: 'M3 4h18v16H3zM12 4v16',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 11v6m0-10v1',
  folder: 'M3 6h7l2 3h9v11H3z',
  alert: 'm12 3 10 18H2ZM12 9v5m0 3v1',
  person: 'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8M4 21v-2a8 8 0 0 1 16 0v2',
}
export function Icon({ name }: { name: IconName }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {paths[name] ? <path d={paths[name]} /> : name === 'inbox' ? <><path d="M4 4h16v16H4z" /><path d="M4 14h5l1 3h4l1-3h5" /></>
      : name === 'diff' ? <><path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M12.5 9v6M9 18h7" /></>
        : <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" /><path d={name === 'close' ? 'm16 9-3 3 3 3' : 'm13 9 3 3-3 3'} /></>}
  </svg>
}
