import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ClaimList, filterClaims } from './ClaimList'
import { recommendationStatus } from './RecommendationList'
import { tocOf } from './ReportPage'
import type { ActionLogDTO, ApprovalDTO, ClaimDTO } from './types'

const claim = (id: number, status: ClaimDTO['status'], isKey = false): ClaimDTO => ({ id, text: `Claim ${id}`, status, confidence: 0.5, isKey, evidenceKeys: [] })
const claims = [claim(1, 'VERIFIED', true), claim(2, 'UNSUPPORTED'), claim(3, 'CONTRADICTED'), claim(4, 'VERIFIED')]

describe('claim filtering', () => {
  it('filters by status in code', () => { expect(filterClaims(claims, 'VERIFIED').map((c) => c.id)).toEqual([1, 4]); expect(filterClaims(claims, 'ALL')).toHaveLength(4) })
  it('filters in the UI, shows counts, and marks key claims', async () => {
    render(<ClaimList claims={claims} evidence={[]} onOpenEvidence={() => {}} />)
    expect(screen.getByRole('button', { name: 'Verified (2)' })).toBeInTheDocument(); expect(screen.getByText('Key claim')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Contradicted (1)' }))
    expect(screen.getByText('Claim 3')).toBeInTheDocument(); expect(screen.queryByText('Claim 1')).toBeNull()
  })
  it('never hides unsupported or contradicted claims under the default filter', () => {
    render(<ClaimList claims={claims} evidence={[]} onOpenEvidence={() => {}} />)
    expect(screen.getByText('Unsupported')).toBeInTheDocument(); expect(screen.getByText('Contradicted')).toBeInTheDocument()
  })
})
describe('recommendation status', () => {
  const ap = (s: ApprovalDTO['status']) => ({ id: 9, actionKey: 'k', status: s }) as ApprovalDTO
  const act = (s: ActionLogDTO['status'], automatic = false) => ({ id: 1, approvalId: automatic ? null : 9, status: s, automatic }) as ActionLogDTO
  const rec = { id: 'r', text: '', risk: 'HIGH' as const, actionKey: 'k' }
  it('covers pending, rejected, expired, approved and executed (simulated)', () => {
    expect(recommendationStatus(rec, [ap('PENDING')], [])?.label).toBe('Pending approval')
    expect(recommendationStatus(rec, [ap('REJECTED')], [])?.label).toBe('Rejected')
    expect(recommendationStatus(rec, [ap('EXPIRED')], [])?.label).toBe('Expired')
    expect(recommendationStatus(rec, [ap('APPROVED')], [])?.label).toBe('Approved')
    expect(recommendationStatus(rec, [ap('APPROVED')], [act('EXECUTED')])?.label).toBe('Executed (simulated)')
  })
  it('shows nothing for recommendations without an action', () => { expect(recommendationStatus({ ...rec, actionKey: null }, [], [])).toBeNull() })
})
describe('table of contents', () => { it('extracts level 2 and 3 headings', () => { expect(tocOf('# T\n## A\ntext\n### B\n## C')).toEqual([{ level: 2, text: 'A' }, { level: 3, text: 'B' }, { level: 2, text: 'C' }]) }) })
