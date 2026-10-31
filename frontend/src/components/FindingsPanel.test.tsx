import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { LanguageProvider } from './LanguageProvider'
import { FindingsPanel } from './FindingsPanel'
import { analysisFixture } from '../test/analysisFixture'
import { translator } from '../lib/i18n'

it.each(['en', 'es'] as const)('discloses findings in %s without requests or losing human drafts', async (language) => {
  localStorage.setItem('ai-change-inspector.language', language)
  const t = translator(language)
  const onReview = vi.fn()
  const second = structuredClone(analysisFixture.findings[0])
  second.hypothesis.title = 'Another hypothesis'
  render(<LanguageProvider><FindingsPanel analysis={{ ...analysisFixture, findings: [analysisFixture.findings[0], second] }} loading={false} error="" canReview={false} onReview={onReview} readOnly renderFeedback={(index) => <textarea aria-label={`Draft ${index}`} />} /></LanguageProvider>)
  const articles = screen.getAllByRole('article')
  const first = within(articles[0]).getByRole('button', { name: t('findingDetails') })
  const next = within(articles[1]).getByRole('button', { name: t('findingDetails') })
  expect(first).toHaveAttribute('aria-expanded', 'true')
  expect(next).toHaveAttribute('aria-expanded', 'false')
  await userEvent.type(screen.getByLabelText('Draft 1'), 'Human draft')
  const toggle = within(articles[1]).getByText(t('findingDetails'))
  toggle.focus()
  expect(toggle).toHaveFocus()
  await userEvent.keyboard('{Enter}')
  expect(next).toHaveAttribute('aria-expanded', 'true')
  expect(within(articles[1]).getByRole('link')).toHaveAttribute('href', '#hunk_test-line-5')
  await userEvent.keyboard('{Enter}')
  expect(next).toHaveAttribute('aria-expanded', 'false')
  expect(screen.getByLabelText('Draft 1')).toHaveValue('Human draft')
  expect(screen.getByLabelText('Draft 1')).toBeVisible()
  expect(onReview).not.toHaveBeenCalled()
})
