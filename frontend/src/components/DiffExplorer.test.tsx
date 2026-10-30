import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { parsedFixture } from '../test/fixture'
import { DiffExplorer } from './DiffExplorer'

it('shows rename, binary and metadata-only changes without fabricated lines', () => {
  const base = parsedFixture.files[0]
  render(<DiffExplorer result={{ additions: 0, deletions: 0, files: [
    { ...base, file_id: 'binary', old_path: 'old.png', new_path: 'new.png', change_type: 'renamed', is_binary: true, hunks: [], metadata: ['rename from old.png', 'rename to new.png'] },
    { ...base, file_id: 'mode', hunks: [], metadata: ['old mode 100644', 'new mode 100755'] },
  ] }} />)
  expect(screen.getByText('From old.png')).toBeInTheDocument()
  expect(screen.getByText(/Binary file/)).toBeInTheDocument()
  expect(screen.getByText(/Metadata change with no modified lines/)).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
