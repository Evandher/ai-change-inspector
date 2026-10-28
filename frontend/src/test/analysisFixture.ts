import type { AnalysisResponse, Reference } from '../types/analysis'
import { parsedFixture } from './fixture'

const reference: Reference = {
  file_id: 'file_test', hunk_id: 'hunk_test', path: 'a.txt', side: 'old',
  line_start: 1, line_end: 1, quote: 'old',
}

export const analysisFixture: AnalysisResponse = {
  model: 'muse-spark-1.3', summary: 'Revisión limitada al cambio mostrado.',
  parsed_diff: parsedFixture,
  findings: [{
    hypothesis: {
      title: 'Posible cambio de contrato', severity: 'medium',
      explanation: '<script>untrusted()</script>', references: [reference],
      suggested_tests: ['Comprobar el contrato con el consumidor.'],
    },
    all_references_valid: true,
    reference_checks: [{ reference, status: 'valid', reason: 'matched', diff_line: 5 }],
  }],
}
