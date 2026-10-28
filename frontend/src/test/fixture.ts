import type { ParsedDiff } from '../types/diff'

export const parsedFixture: ParsedDiff = {
  additions: 1, deletions: 1,
  files: [{
    file_id: 'file_test', old_path: 'a.txt', new_path: 'a.txt', change_type: 'modified',
    is_binary: false, metadata: [], additions: 1, deletions: 1,
    hunks: [{
      hunk_id: 'hunk_test', header: '@@ -1 +1 @@', old_start: 1, old_count: 1,
      new_start: 1, new_count: 1,
      lines: [
        { kind: 'deletion', content: 'old', old_line: 1, new_line: null, diff_line: 5, no_newline: false },
        { kind: 'addition', content: '<script>alert(1)</script>', old_line: null, new_line: 1, diff_line: 6, no_newline: true },
      ],
    }],
  }],
}
