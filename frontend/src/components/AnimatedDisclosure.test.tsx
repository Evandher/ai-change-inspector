import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { AnimatedDisclosure } from './AnimatedDisclosure'

it('supports rapid keyboard reversal without unmounting content or losing focus', async () => {
  render(<AnimatedDisclosure label="Details"><input aria-label="Draft" defaultValue="Keep me" /></AnimatedDisclosure>)
  const toggle = screen.getByRole('button', { name: 'Details' })
  const content = document.getElementById(toggle.getAttribute('aria-controls')!)!
  const input = screen.getByLabelText('Draft')
  expect(content).toHaveAttribute('inert')
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  toggle.focus()
  await userEvent.keyboard('{Enter}{Enter}{Enter}')
  expect(toggle).toHaveFocus()
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(content).not.toHaveAttribute('inert')
  expect(screen.getByRole('textbox')).toBe(input)
  await userEvent.type(input, ' edited')
  await userEvent.click(toggle)
  expect(content).toHaveAttribute('aria-hidden', 'true')
  expect(content).toHaveAttribute('inert')
  expect(input).toHaveValue('Keep me edited')
  await userEvent.keyboard(' ')
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByRole('textbox')).toBe(input)
})

it('gives independent disclosures unique accessible targets', async () => {
  render(<><AnimatedDisclosure label="Parent" defaultOpen>Parent evidence</AnimatedDisclosure><AnimatedDisclosure label="Child">Child evidence</AnimatedDisclosure></>)
  const parent = screen.getByRole('button', { name: 'Parent' })
  const child = screen.getByRole('button', { name: 'Child' })
  expect(parent.getAttribute('aria-controls')).not.toBe(child.getAttribute('aria-controls'))
  await userEvent.click(child)
  expect(parent).toHaveAttribute('aria-expanded', 'true')
  expect(child).toHaveAttribute('aria-expanded', 'true')
})
