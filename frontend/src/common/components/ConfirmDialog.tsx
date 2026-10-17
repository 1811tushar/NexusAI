import { useState, type ReactNode } from 'react'
import { Dialog, DialogContent } from './ui/Dialog'
import { Button } from './ui/Button'
import { Input } from './ui/Input'

interface Props {
  open: boolean; onOpenChange: (o: boolean) => void
  title: string; description: ReactNode; confirmLabel: string
  onConfirm: () => Promise<void> | void
  danger?: boolean
  /** If set, the user must type this exact text to enable confirm. */
  typedConfirmation?: string
}
export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel, onConfirm, danger, typedConfirmation }: Props) {
  const [busy, setBusy] = useState(false)
  const [typed, setTyped] = useState('')
  const ok = !typedConfirmation || typed === typedConfirmation
  const go = async () => { setBusy(true); try { await onConfirm(); onOpenChange(false); setTyped('') } finally { setBusy(false) } }
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!busy) { onOpenChange(o); if (!o) setTyped('') } }}>
      <DialogContent title={title}>
        <div className="space-y-4">
          <div className="text-sm text-muted">{description}</div>
          {typedConfirmation && <Input label={`Type ${typedConfirmation} to confirm`} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
            <Button variant={danger ? 'danger' : 'primary'} onClick={go} loading={busy} disabled={!ok}>{confirmLabel}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
