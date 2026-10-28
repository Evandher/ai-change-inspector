import modified from '../../../examples/diffs/modified.diff?raw'
import multiple from '../../../examples/diffs/multiple-files.diff?raw'
import metadata from '../../../examples/diffs/metadata.diff?raw'

export const examples = [
  { label: 'Cambio simple', diff: modified },
  { label: 'Varios archivos', diff: multiple },
  { label: 'Metadatos', diff: metadata },
]
