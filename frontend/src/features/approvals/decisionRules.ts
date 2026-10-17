import type { ApprovalStatus, Role } from '@/common/types/api'
/** Why the current user cannot decide, or null if they can. The server remains the authority (self-approval is also enforced there). */
export function decisionBlockReason(a: { role: Role; userId: number; ownerId?: number; status: ApprovalStatus }): string | null {
  if (a.status !== 'PENDING') return 'This approval has already been decided or has expired.'
  if (a.role === 'ANALYST') return 'Only approvers and administrators can decide approvals.'
  if (a.ownerId !== undefined && a.ownerId === a.userId) return 'You started this investigation, so you cannot approve its actions. Another approver must decide.'
  return null
}
export const canContinue = (choice: 'APPROVE' | 'REJECT' | null, comment: string) => choice === 'APPROVE' || (choice === 'REJECT' && comment.trim().length > 0)
