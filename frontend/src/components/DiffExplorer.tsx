import { useLanguage } from '../lib/i18n'
import { Fragment } from 'react'
import type { DiffFile, ParsedDiff } from '../types/diff'
import { CodeText } from './CodeText'
import { Icon } from './Icon'

const lineClasses = { context: 'text-primary', addition: 'bg-success-soft text-primary', deletion: 'bg-danger-soft text-primary' }
const lineSigns = { context: ' ', addition: '+', deletion: '−' }

function FileView({ file, idPrefix }: { file: DiffFile; idPrefix: string }) {
  const { t } = useLanguage()
  return (
    <article id={`${idPrefix}${file.file_id}`} className="diff-file overflow-hidden rounded-lg border border-edge bg-panel">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-edge px-4 py-4">
        <div className="min-w-0"><h3 className="file-heading break-all font-mono text-sm font-semibold text-primary"><Icon name="file" /><a href={`#${idPrefix}${file.file_id}`}>{file.new_path ?? file.old_path}</a></h3>
          {file.old_path && file.new_path && file.old_path !== file.new_path && <p className="mt-1 break-all font-mono text-xs text-secondary">{t('from')} {file.old_path}</p>}
        </div>
        <div className="flex gap-3 text-xs"><span className="text-secondary">{t(file.change_type)}</span><span className="text-success">+{file.additions}</span><span className="text-danger">−{file.deletions}</span></div>
      </header>
      {file.metadata.length > 0 && <details className="border-b border-edge px-4 py-3 text-xs text-secondary"><summary className="cursor-pointer">{t('fileMetadata')}</summary><pre className="mt-3 overflow-x-auto leading-6">{file.metadata.join('\n')}</pre></details>}
      {file.is_binary ? <p className="p-5 text-sm text-secondary">{t('binary')}</p>
        : file.hunks.length === 0 ? <p className="p-5 text-sm text-secondary">{t('metadataOnly')}</p>
          : file.hunks.map((hunk) => (
            <section key={hunk.hunk_id} id={`${idPrefix}${hunk.hunk_id}`} aria-label={hunk.header}>
              <h4 className="overflow-x-auto bg-info-soft px-4 py-2 font-mono text-xs whitespace-pre text-info">{hunk.header}</h4>
              <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t('lines', { path: file.new_path ?? file.old_path ?? '' })}>
                <table className="w-full border-collapse font-mono text-xs leading-6" aria-label={t('diffTable')}>
                  <thead className="sr-only"><tr><th>{t('old')}</th><th>{t('new')}</th><th>{t('type')}</th><th>{t('content')}</th></tr></thead>
                  <tbody>{hunk.lines.map((line) => (
                    <Fragment key={line.diff_line}>
                      <tr id={`${idPrefix}${hunk.hunk_id}-line-${line.diff_line}`} data-file-id={file.file_id} data-hunk-id={hunk.hunk_id} className={lineClasses[line.kind]}>
                        <td className="w-12 border-r border-edge/60 px-3 text-right align-top text-muted select-none">{line.old_line}</td>
                        <td className="w-12 border-r border-edge/60 px-3 text-right align-top text-muted select-none">{line.new_line}</td>
                        <td className="w-8 px-2 align-top select-none">{lineSigns[line.kind]}</td>
                        <td className="pr-4 whitespace-pre"><CodeText text={line.content || '\u00a0'} path={file.new_path ?? file.old_path ?? ''} /></td>
                      </tr>
                      {line.no_newline && <tr><td colSpan={4} className="px-4 italic text-warning">{t('noNewline')}</td></tr>}
                    </Fragment>
                  ))}</tbody>
                </table>
              </div>
            </section>
          ))}
    </article>
  )
}

export function DiffExplorer({ result, idPrefix = '' }: { result: ParsedDiff | null; idPrefix?: string }) {
  const { t } = useLanguage()
  return (
    <section aria-labelledby={`${idPrefix}explorer-title`} className="min-w-0">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${idPrefix}explorer-title`} className="text-lg font-semibold text-primary">{t('explorer')}</h2>
        {result && <p role="status" className="text-sm text-secondary">{t('files', { count: result.files.length })} <span className="ml-3 text-success">+{result.additions}</span> <span className="ml-2 text-danger">−{result.deletions}</span></p>}
      </div>
      {result ? <div className="space-y-4">
        {result.files.length > 1 && <nav aria-label={t('diffFiles')} className="flex flex-wrap gap-2">{result.files.map((file) => <a key={file.file_id} href={`#${idPrefix}${file.file_id}`} className="secondary-button break-all">{file.new_path ?? file.old_path}</a>)}</nav>}
        {result.files.map((file) => <FileView key={file.file_id} file={file} idPrefix={idPrefix} />)}
      </div> : <div className="rounded-lg border border-edge bg-panel/40 px-6 py-16 text-center"><p className="font-medium text-primary">{t('start')}</p><p className="mt-2 text-sm text-muted">{t('startHelp')}</p></div>}
    </section>
  )
}
