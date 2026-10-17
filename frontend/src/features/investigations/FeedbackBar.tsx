import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { isApiError } from '@/common/api/errors'
import { Button } from '@/common/components/ui/Button'
import { Textarea } from '@/common/components/ui/Textarea'
import { toast } from '@/common/components/ui/toastStore'
import { cn } from '@/common/utils/cn'
import { investigationApi } from './investigationApi'

export function FeedbackBar({ id, initial }: { id: number; initial: 1 | -1 | null }) {
  const [rating, setRating] = useState<1 | -1 | null>(initial)
  const [comment, setComment] = useState(''); const [sent, setSent] = useState(initial !== null)
  const send = useMutation({
    mutationFn: () => investigationApi.feedback(id, { rating: rating as 1 | -1, comment: comment.trim() || undefined }),
    onSuccess: () => { setSent(true); toast.success('Thanks for the feedback') },
    onError: (e) => toast.error('Feedback not sent', isApiError(e) ? e.display : undefined),
  })
  const pick = (r: 1 | -1) => { setRating(r); setSent(false) }
  const btn = (r: 1 | -1, label: string, Icon: typeof ThumbsUp) => (
    <Button variant="secondary" size="sm" aria-pressed={rating === r} aria-label={label} onClick={() => pick(r)} className={cn(rating === r && 'border-accent bg-accent-soft')}><Icon className="h-4 w-4" aria-hidden />{r === 1 ? 'Helpful' : 'Not helpful'}</Button>)
  return (
    <section aria-label="Feedback" className="space-y-2 rounded-lg border border-line bg-surface p-3" data-no-print>
      <p className="text-sm font-medium">Was this report useful?</p>
      <div className="flex gap-2">{btn(1, 'Mark this report as helpful', ThumbsUp)}{btn(-1, 'Mark this report as not helpful', ThumbsDown)}</div>
      {rating !== null && !sent && (<><Textarea label="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} /><Button size="sm" loading={send.isPending} onClick={() => send.mutate()}>Send feedback</Button></>)}
      {sent && <p className="text-sm text-muted">Feedback recorded.</p>}
    </section>
  )
}
