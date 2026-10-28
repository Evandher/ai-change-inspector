export function FindingsPanel() {
  return (
    <aside aria-labelledby="findings-title" className="rounded-2xl border border-dashed border-slate-700 p-6">
      <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Próximamente · Sprint 2</span>
      <h2 id="findings-title" className="mt-3 text-lg font-semibold text-slate-300">Hallazgos de IA</h2>
      <p className="mt-3 text-sm leading-6 text-slate-400">Este espacio reunirá los hallazgos vinculados a archivos y líneas del diff.</p>
      <p className="mt-4 text-xs leading-5 text-slate-500">El análisis con modelos todavía no está disponible.</p>
    </aside>
  )
}
