import modified from '../../../examples/diffs/modified.diff?raw'
import multiple from '../../../examples/diffs/multiple-files.diff?raw'
import metadata from '../../../examples/diffs/metadata.diff?raw'

export const examples = [
  { label: 'simple' as const, diff: modified },
  { label: 'multiple' as const, diff: multiple },
  { label: 'metadata' as const, diff: metadata },
]
