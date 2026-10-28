import { Fragment } from 'react'
import type { DiffFile, ParsedDiff } from '../types/diff'

const changeLabels = { added: 'Agregado', deleted: 'Eliminado', modified: 'Modificado', renamed: 'Renombrado', copied: 'Copiado' }
const lineClasses = { context: 'text-slate-300', addition: 'bg-emerald-950/60 text-emerald-200', deletion: 'bg-rose-950/50 text-rose-200' }
const lineSigns = { context: ' ', addition: '+', deletion: '−' }

function FileView({ file }: { file: DiffFile }) {
  return (
    <article id={file.file_id} className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-4 py-4">
        <div className="min-w-0"><h3 className="break-all font-mono text-sm font-semibold text-white">{file.new_path ?? file.old_path}</h3>
          {file.old_path && file.new_path && file.old_path !== file.new_path && <p className="mt-1 break-all font-mono text-xs text-slate-400">Desde {file.old_path}</p>}
        </div>
        <div className="flex gap-3 text-xs"><span className="text-slate-400">{changeLabels[file.change_type]}</span><span className="text-emerald-300">+{file.additions}</span><span className="text-rose-300">−{file.deletions}</span></div>
      </header>
      {file.metadata.length > 0 && <details className="border-b border-slate-800 px-4 py-3 text-xs text-slate-400"><summary className="cursor-pointer">Metadatos del archivo</summary><pre className="mt-3 overflow-x-auto leading-6">{file.metadata.join('\n')}</pre></details>}
      {file.is_binary ? <p className="p-5 text-sm text-slate-400">Archivo binario · El contenido no se interpreta.</p>
        : file.hunks.length === 0 ? <p className="p-5 text-sm text-slate-400">Cambio de metadatos sin líneas modificadas.</p>
          : file.hunks.map((hunk) => (
            <section key={hunk.hunk_id} id={hunk.hunk_id} aria-label={hunk.header}>
              <h4 className="overflow-x-auto bg-sky-950/40 px-4 py-2 font-mono text-xs whitespace-pre text-sky-300">{hunk.header}</h4>
              <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`Líneas de ${file.new_path ?? file.old_path}`}>
                <table className="w-full border-collapse font-mono text-xs leading-6" aria-label="Diff: líneas anteriores, nuevas y contenido">
                  <thead className="sr-only"><tr><th>Anterior</th><th>Nueva</th><th>Tipo</th><th>Contenido</th></tr></thead>
                  <tbody>{hunk.lines.map((line) => (
                    <Fragment key={line.diff_line}>
                      <tr id={`${hunk.hunk_id}-line-${line.diff_line}`} data-file-id={file.file_id} data-hunk-id={hunk.hunk_id} className={lineClasses[line.kind]}>
                        <td className="w-12 border-r border-slate-800/60 px-3 text-right align-top text-slate-500 select-none">{line.old_line}</td>
                        <td className="w-12 border-r border-slate-800/60 px-3 text-right align-top text-slate-500 select-none">{line.new_line}</td>
                        <td className="w-8 px-2 align-top select-none">{lineSigns[line.kind]}</td>
                        <td className="pr-4 whitespace-pre">{line.content || '\u00a0'}</td>
                      </tr>
                      {line.no_newline && <tr><td colSpan={4} className="px-4 italic text-amber-200">\ No newline at end of file</td></tr>}
                    </Fragment>
                  ))}</tbody>
                </table>
              </div>
            </section>
          ))}
    </article>
  )
}

export function DiffExplorer({ result }: { result: ParsedDiff | null }) {
  return (
    <section aria-labelledby="explorer-title" className="min-w-0">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 id="explorer-title" className="text-lg font-semibold text-white">Explorador de cambios</h2>
        {result && <p role="status" className="text-sm text-slate-400">{result.files.length} archivo(s) <span className="ml-3 text-emerald-300">+{result.additions}</span> <span className="ml-2 text-rose-300">−{result.deletions}</span></p>}
      </div>
      {result ? <div className="space-y-4">
        <nav aria-label="Archivos del diff" className="flex flex-wrap gap-2">{result.files.map((file) => <a key={file.file_id} href={`#${file.file_id}`} className="secondary-button break-all">{file.new_path ?? file.old_path}</a>)}</nav>
        {result.files.map((file) => <FileView key={file.file_id} file={file} />)}
      </div> : <div className="rounded-2xl border border-slate-800 bg-slate-900/40 px-6 py-16 text-center"><p className="font-medium text-slate-300">Tu próximo cambio empieza aquí</p><p className="mt-2 text-sm text-slate-500">Pega un diff o carga un ejemplo para explorar sus archivos y líneas.</p></div>}
    </section>
  )
}
