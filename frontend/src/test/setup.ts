import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'

beforeEach(() => { window.history.replaceState(null, '', '/diff') })

afterEach(() => {
  cleanup()
  localStorage.clear()
  document.documentElement.lang = 'en'
  window.history.replaceState(null, '', '/')
})
