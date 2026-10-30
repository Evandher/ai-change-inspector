import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { LANGUAGE_KEY, savedLanguage, translator } from './lib/i18n'
import { en, es } from './lib/translations'
import type { TranslationKey } from './lib/translations'
import { DisplayError, errorText } from './lib/errors'
import { reviewFixture } from './test/reviewFixture'

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })
const json = (data: unknown) => new Response(JSON.stringify(data))

it('has complete EN/ES catalogs, including matching interpolation parameters', () => {
  expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort())
  for (const key of Object.keys(en) as TranslationKey[]) {
    expect(en[key].trim()).not.toBe('')
    expect(es[key].trim()).not.toBe('')
    expect(es[key].match(/\{\w+\}/g) ?? []).toEqual(en[key].match(/\{\w+\}/g) ?? [])
  }
  expect(translator('en')('pagination', { start: 1, end: 20, total: 42 })).toBe('1–20 of 42')
  expect(translator('es')('pagination', { start: 1, end: 20, total: 42 })).toBe('1–20 de 42')
})

it('defaults to English regardless of browser language and uses an accessible selector', () => {
  vi.spyOn(navigator, 'language', 'get').mockReturnValue('es')
  render(<App />)
  expect(screen.getByRole('combobox', { name: 'Interface language' })).toHaveValue('en')
  expect(document.documentElement).toHaveAttribute('lang', 'en')
  for (const key of ['inspect', 'explorer', 'findings'] as const) {
    expect(screen.getByRole('heading', { name: en[key] })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: es[key] })).not.toBeInTheDocument()
  }
  expect(screen.getByText(en.creditsHelp)).toBeInTheDocument()
})

it('persists ES through navigation and remount and can restore EN', async () => {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json({ items: [], total: 0 })))
  vi.stubGlobal('fetch', fetchMock)
  const first = render(<App />)
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /Interface language|Idioma de la interfaz/ }), 'es')
  expect(localStorage.getItem(LANGUAGE_KEY)).toBe('es')
  await userEvent.click(screen.getByRole('link', { name: es.inbox }))
  expect(await screen.findByText(es.emptyInbox)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: es.refreshInbox })).toBeInTheDocument()
  first.unmount()
  render(<App />)
  expect(screen.getByRole('combobox', { name: es.language })).toHaveValue('es')
  expect(await screen.findByText(es.emptyInbox)).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /Interface language|Idioma de la interfaz/ }), 'en')
  expect(screen.getByText(en.emptyInbox)).toBeInTheDocument()
  expect(document.documentElement).toHaveAttribute('lang', 'en')
  expect(localStorage.getItem(LANGUAGE_KEY)).toBe('en')
  expect(fetchMock).toHaveBeenCalledTimes(2) // Mounts only; language changes do not fetch.
})

it('uses English for unsupported saved preferences', () => {
  localStorage.setItem(LANGUAGE_KEY, 'fr')
  expect(savedLanguage()).toBe('en')
  render(<App />)
  expect(screen.getByRole('combobox', { name: /Interface language|Idioma de la interfaz/ })).toHaveValue('en')
})

it('remains usable for the session when localStorage is blocked', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  render(<App />)
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /Interface language|Idioma de la interfaz/ }), 'es')
  expect(screen.getByRole('heading', { name: es.inspect })).toBeInTheDocument()
})

it('translates an already displayed validation error without another request', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: en.parse }))
  expect(screen.getByRole('alert')).toHaveTextContent(en.empty_diff)
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /Interface language|Idioma de la interfaz/ }), 'es')
  expect(screen.getByRole('alert')).toHaveTextContent(es.empty_diff)
  expect(fetchMock).not.toHaveBeenCalled()
})

it('preserves historical findings, suggested tests, quotes and diff across UI language changes', async () => {
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  const fetchMock = vi.fn().mockResolvedValue(json(reviewFixture))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  const hypothesis = reviewFixture.analysis!.findings[0].hypothesis
  expect(await screen.findByText(hypothesis.title)).toBeInTheDocument()
  for (const language of ['es', 'en'] as const) {
    await userEvent.selectOptions(screen.getByRole('combobox', { name: /Interface language|Idioma de la interfaz/ }), language)
    const t = translator(language)
    expect(screen.getByRole('heading', { name: t('detail') })).toBeInTheDocument()
    expect(screen.getByText(t('completed'))).toBeInTheDocument()
    expect(screen.getByText(`${t('severity')} ${t(hypothesis.severity)}`)).toBeInTheDocument()
    expect(screen.getByText(t('validReferences'))).toBeInTheDocument()
    expect(screen.getByText(hypothesis.title)).toBeInTheDocument()
    expect(screen.getByText(hypothesis.explanation)).toBeInTheDocument()
    expect(screen.getByText(hypothesis.suggested_tests[0])).toBeInTheDocument()
    expect(screen.getByLabelText(t('originalDiff'))).toHaveValue(reviewFixture.diff)
  }
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it.each(['en', 'es'] as const)('renders pending controls and provider errors in %s', async (language) => {
  localStorage.setItem(LANGUAGE_KEY, language)
  const t = translator(language)
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  const fetchMock = vi.fn().mockResolvedValue(json({ ...reviewFixture, status: 'pending', analysis: null }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  expect(await screen.findByRole('button', { name: t('analyzePending') })).toBeInTheDocument()
  expect(screen.getByText(t('pendingCredits'))).toBeInTheDocument()
  expect(screen.queryByText(translator(language === 'en' ? 'es' : 'en')('pendingCredits'))).not.toBeInTheDocument()
  fetchMock.mockResolvedValue(json({ ...reviewFixture, status: 'error', analysis: null, error: { code: 'model_timeout', message: 'Original error stored in another language.' } }))
  await userEvent.click(screen.getByRole('button', { name: t('refreshReview') }))
  expect(await screen.findByRole('alert')).toHaveTextContent(t('model_timeout'))
})

it('localizes API error codes and line numbers without changing or exposing raw messages', () => {
  const error = new DisplayError('invalid_hunk', 4)
  expect(errorText(error, translator('en'))).toBe(`${en.invalid_hunk} Line 4.`)
  expect(errorText(error, translator('es'))).toBe(`${es.invalid_hunk} Línea 4.`)
  expect(errorText({ code: 'future_error', message: 'Raw server text' }, translator('en'))).toBe(`${en.unknownError} (future_error)`)
})
