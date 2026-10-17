import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/common/api/errors'
import type { ApprovalDTO } from '@/features/investigations/types'
import { DecisionDialog } from './DecisionDialog'
import { approvalApi } from './approvalApi'
import { canContinue, decisionBlockReason } from './decisionRules'

vi.mock('./approvalApi', () => ({ approvalApi: { decide: vi.fn() } }))
const approval = (p: Partial<ApprovalDTO> = {}): ApprovalDTO => ({ id: 5, investigationId: 1, investigationQuestion: 'Q', actionKey: 'k', actionType: 'ADJUST_PRICE', title: 'Reduce price', description: 'Lower the price', params: { productId: 7, changePct: -8 },
  risk: 'HIGH', rationale: 'Because', evidenceKeys: [], confidence: 0.8, status: 'PENDING', requestedAt: new Date().toISOString(), decidedBy: null, decidedAt: null, comment: null, ...p })
const setup = (props: Partial<Parameters<typeof DecisionDialog>[0]> = {}) => {
  const onOpenChange = vi.fn()
  render(<QueryClientProvider client={new QueryClient()}><DecisionDialog approval={approval()} role="APPROVER" userId={2} open onOpenChange={onOpenChange} {...props} /></QueryClientProvider>)
  return { user: userEvent.setup(), onOpenChange }
}
beforeEach(() => vi.mocked(approvalApi.decide).mockReset())

describe('decision rules', () => {
  it('blocks analysts, self-approval and already-decided approvals', () => {
    expect(decisionBlockReason({ role: 'ANALYST', userId: 1, status: 'PENDING' })).toMatch(/Only approvers/)
    expect(decisionBlockReason({ role: 'ADMIN', userId: 3, ownerId: 3, status: 'PENDING' })).toMatch(/cannot approve/)
    expect(decisionBlockReason({ role: 'APPROVER', userId: 2, status: 'APPROVED' })).toMatch(/already been decided/)
    expect(decisionBlockReason({ role: 'APPROVER', userId: 2, ownerId: 1, status: 'PENDING' })).toBeNull()
  })
  it('requires a comment to reject but not to approve', () => {
    expect(canContinue('APPROVE', '')).toBe(true); expect(canContinue('REJECT', '  ')).toBe(false); expect(canContinue('REJECT', 'why')).toBe(true); expect(canContinue(null, 'x')).toBe(false)
  })
})
describe('DecisionDialog', () => {
  it('rejecting needs a reason, then shows what will happen and submits it', async () => {
    vi.mocked(approvalApi.decide).mockResolvedValue(approval({ status: 'REJECTED' }))
    const { user } = setup()
    await user.click(screen.getByLabelText('Reject'))
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
    await user.type(screen.getByLabelText(/Reason/), 'Stock has recovered')
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByText(/will not be executed|not.*be executed/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Confirm rejection' }))
    expect(approvalApi.decide).toHaveBeenCalledWith(5, { decision: 'REJECT', comment: 'Stock has recovered' })
  })
  it('approving states that execution is simulated before confirming', async () => {
    vi.mocked(approvalApi.decide).mockResolvedValue(approval({ status: 'APPROVED' }))
    const { user } = setup()
    await user.click(screen.getByLabelText('Approve')); await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByText(/simulated execution/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Confirm approval' }))
    expect(approvalApi.decide).toHaveBeenCalledWith(5, { decision: 'APPROVE', comment: undefined })
  })
  it('explains and offers no controls for self-approval', () => {
    setup({ role: 'ADMIN', userId: 3, ownerId: 3 })
    expect(screen.getByText(/cannot approve its actions/)).toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Continue' })).toBeNull()
  })
  it('explains and offers no controls for roles without permission', () => {
    setup({ role: 'ANALYST', userId: 1 })
    expect(screen.getByText(/Only approvers and administrators/)).toBeInTheDocument(); expect(screen.queryByLabelText('Approve')).toBeNull()
  })
  it('closes and refreshes when the approval was already decided (INVALID_STATE)', async () => {
    vi.mocked(approvalApi.decide).mockRejectedValue(new ApiError('INVALID_STATE', 'Already decided', 409))
    const { user, onOpenChange } = setup()
    await user.click(screen.getByLabelText('Approve')); await user.click(screen.getByRole('button', { name: 'Continue' })); await user.click(screen.getByRole('button', { name: 'Confirm approval' }))
    await vi.waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
  })
  it('shows the self-approval error returned by the server inline', async () => {
    vi.mocked(approvalApi.decide).mockRejectedValue(new ApiError('SELF_APPROVAL_NOT_ALLOWED', 'x', 403))
    const { user } = setup()
    await user.click(screen.getByLabelText('Approve')); await user.click(screen.getByRole('button', { name: 'Continue' })); await user.click(screen.getByRole('button', { name: 'Confirm approval' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/investigation you started/)
  })
})
