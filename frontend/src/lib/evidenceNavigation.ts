import { createContext, useContext } from 'react'
import type { Reference } from '../types/analysis'

export interface EvidenceSelection {
  reference: Reference
  title: string
  originId: string
  targetId: string
}
export const EvidenceContext = createContext<{
  selected: EvidenceSelection | null
  scope?: string
  activate: (selection: EvidenceSelection) => void
  back: () => void
} | null>(null)
export const useEvidenceNavigation = () => useContext(EvidenceContext)
