import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { CodeText } from './CodeText'

it('highlights supported source while preserving exact text and whitespace as safe React text', () => {
  const text = '    return "<script>alert(1)</script>" + 42'
  render(<pre data-testid="code"><CodeText text={text} path="src/test.py" /></pre>)
  expect(screen.getByTestId('code').textContent).toBe(text)
  expect(screen.getByText('return')).toHaveClass('syntax-keyword')
  expect(document.querySelector('script')).toBeNull()
})

it('leaves unsupported file formats as literal text', () => {
  render(<pre data-testid="code"><CodeText text="return 42" path="notes.txt" /></pre>)
  expect(screen.getByTestId('code').textContent).toBe('return 42')
  expect(screen.getByTestId('code').querySelector('span')).toBeNull()
})
