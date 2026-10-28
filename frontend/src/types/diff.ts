export interface DiffLine {
  kind: 'context' | 'addition' | 'deletion'
  content: string
  old_line: number | null
  new_line: number | null
  diff_line: number
  no_newline: boolean
}

export interface Hunk {
  hunk_id: string
  header: string
  old_start: number
  old_count: number
  new_start: number
  new_count: number
  lines: DiffLine[]
}

export interface DiffFile {
  file_id: string
  old_path: string | null
  new_path: string | null
  change_type: 'added' | 'deleted' | 'modified' | 'renamed' | 'copied'
  is_binary: boolean
  metadata: string[]
  hunks: Hunk[]
  additions: number
  deletions: number
}

export interface ParsedDiff {
  files: DiffFile[]
  additions: number
  deletions: number
}
