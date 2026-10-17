import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { isApiError } from '@/common/api/errors'
import { RiskBadge } from '@/common/components/RiskBadge'
import { Button } from '@/common/components/ui/Button'
import { Dialog, DialogContent } from '@/common/components/ui/Dialog'
import { Textarea } from '@/common/components/ui/Textarea'
import { toast } from '@/common/components/ui/toastStore'
import type { Role } from '@/common/types/api'
import { formatParam, humanizeKey } from '@/features/investigations/labels'
import type { ApprovalDTO } from '@/features/investigations/types'
import { approvalApi } from './approvalApi'
import { canContinue, decisionBlockReason } from './decisionRules'

interface Props { approval: ApprovalDTO; role: Role; userId: number; ownerId?: number; open: boolean; onOpenChange: (o: boolean) => void }
/** Two steps: choose (comment required on reject), then confirm with a plain "simulated execution" summary. */
export function DecisionDialog({ approval: a, role, userId, ownerId, open, onOpenChange }: Props) {
  const qc = useQueryClient()
  const [choice, setChoice] = useState<'APPROVE' | 'REJECT' | null>(null)
  const [comment, setComment] = useState(''); const [step, setStep] = useState<1 | 2>(1); const [serverError, setServerError] = useState<string | null>(null)
  const block = decisionBlockReason({ role, userId, ownerId, status: a.status })
  const reset = () => { setChoice(null); setComment(''); setStep(1); setServerError(null) }
  const refresh = () => { for (const k of ['approvals', 'investigation', 'investigations', 'dashboard']) void qc.invalidateQueries({ queryKey: [k] }) }

  const decide = useMutation({
    mutationFn: () => approvalApi.decide(a.id, { decision: choice as 'APPROVE' | 'REJECT', comment: comment.trim() || undefined }),
    onSuccess: () => { toast.success(choice === 'APPROVE' ? 'Approved. Execution is simulated.' : 'Rejected. Nothing will be executed.'); refresh(); onOpenChange(false); reset() },
    onError: (e) => {
      if (isApiError(e) && e.code === 'INVALID_STATE') { toast.info('Already decided or expired', 'The list has been refreshed.'); refresh(); onOpenChange(false); reset(); return }
      setServerError(isApiError(e) ? (e.code === 'SELF_APPROVAL_NOT_ALLOWED' ? 'You cannot approve actions from an investigation you started. Another approver must decide.' : e.display) : 'The decision could not be saved.'); setStep(1)
    },
  })
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!decide.isPending) { onOpenChange(o); if (!o) reset() } }}>
      <DialogContent title={`Decide: ${a.title}`} description={a.description}>
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm"><RiskBadge risk={a.risk} /><span className="text-muted">{a.rationale}</span></div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">{Object.entries(a.params).map(([k, v]) => (<div key={k} className="contents"><dt className="text-muted">{humanizeKey(k)}</dt><dd>{formatParam(k, v)}</dd></div>))}</dl>
          {block ? <p role="status" className="rounded-md border border-line bg-bg p-3 text-sm">{block}</p> : step === 1 ? (
            <>
              <fieldset className="space-y-2"><legend className="text-sm font-medium">Your decision</legend>
                {(['APPROVE', 'REJECT'] as const).map((c) => (<label key={c} className="flex items-center gap-2 text-sm"><input type="radio" name="decision" className="accent-[var(--accent)]" checked={choice === c} onChange={() => setChoice(c)} />{c === 'APPROVE' ? 'Approve' : 'Reject'}</label>))}</fieldset>
              <Textarea label={choice === 'REJECT' ? 'Reason (required)' : 'Comment (optional)'} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500}
                error={choice === 'REJECT' && comment.trim().length === 0 ? 'Explain why this is rejected' : undefined} />
              {serverError && <p role="alert" className="text-sm text-danger">{serverError}</p>}
              <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button disabled={!canContinue(choice, comment)} onClick={() => setStep(2)}>Continue</Button></div>
            </>
          ) : (
            <>
              <p className="rounded-md border border-line bg-bg p-3 text-sm">{choice === 'APPROVE' ? <>Approving will run <b>{a.title}</b> as a <b>simulated execution</b>. No external system will be changed. The decision and your name are recorded.</> : <>Rejecting means <b>{a.title}</b> will <b>not</b> be executed. Your reason is recorded: “{comment.trim()}”.</>}</p>
              <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setStep(1)} disabled={decide.isPending}>Back</Button>
                <Button variant={choice === 'REJECT' ? 'danger' : 'primary'} loading={decide.isPending} onClick={() => decide.mutate()}>{choice === 'APPROVE' ? 'Confirm approval' : 'Confirm rejection'}</Button></div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
