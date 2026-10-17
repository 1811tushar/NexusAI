import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { isApiError } from '@/common/api/errors'
import { Button } from '@/common/components/ui/Button'
import { Card } from '@/common/components/ui/Card'
import { Checkbox } from '@/common/components/ui/Checkbox'
import { Select } from '@/common/components/ui/Select'
import { Switch } from '@/common/components/ui/Switch'
import { Textarea } from '@/common/components/ui/Textarea'
import { toast } from '@/common/components/ui/toastStore'
import { documentApi } from '@/features/documents/documentApi'
import { investigationApi } from './investigationApi'
import { watchRun } from './runWatcher'

export const HERO_QUESTION = 'Why did Q2 revenue decline compared to Q1, and what should management investigate?'
const examples = [HERO_QUESTION, 'Which region grew in Q2 2026?', 'What was our gross margin by product category last quarter?', 'Which marketing channels should we review?']
const schema = z.object({ question: z.string().trim().min(10, 'Write at least 10 characters').max(2000, 'Keep it under 2000 characters') })
type Form = z.infer<typeof schema>

export function QuestionForm() {
  const nav = useNavigate(); const qc = useQueryClient()
  const prefill = (useLocation().state as { question?: string } | null)?.question ?? ''
  const [web, setWeb] = useState(true); const [memory, setMemory] = useState(true); const [loops, setLoops] = useState('3'); const [scoped, setScoped] = useState<number[]>([])
  const { register, handleSubmit, setValue, setError, watch, formState: { errors, isValid } } = useForm<Form>({ resolver: zodResolver(schema), mode: 'onChange', defaultValues: { question: prefill } })
  const docs = useQuery({ queryKey: ['documents', 'ready-all'], queryFn: () => documentApi.list({ status: 'READY', size: 100 }) })

  const start = useMutation({
    mutationFn: (v: Form) => investigationApi.start({ question: v.question.trim(), options: { webSearch: web, useMemory: memory, maxLoops: Number(loops), ...(scoped.length ? { documentIds: scoped } : {}) } }),
    onSuccess: (inv) => { watchRun(inv.id, inv.question); void qc.invalidateQueries({ queryKey: ['investigations'] }); void qc.invalidateQueries({ queryKey: ['dashboard'] }); nav(`/investigations/${inv.id}`) },
    onError: (e) => {
      if (!isApiError(e)) return toast.error('Could not start the investigation')
      if (e.details?.question) setError('question', { message: e.details.question })
      toast.error(e.code === 'RATE_LIMITED' ? 'Too many investigations' : 'Could not start the investigation', e.display)
    },
  })
  const toggleDoc = (id: number, on: boolean) => setScoped((s) => (on ? [...s, id] : s.filter((x) => x !== id)))

  return (
    <form onSubmit={handleSubmit((v) => start.mutate(v))} className="space-y-4" noValidate>
      <Card className="space-y-3">
        <Textarea label="Your question" hint={`${watch('question')?.trim().length ?? 0} of 2000 characters. Between 10 and 2000.`} rows={4} maxLength={2000} error={errors.question?.message} {...register('question')} />
        <div><p className="mb-1 text-sm font-medium">Try an example</p>
          <ul className="flex flex-wrap gap-2">{examples.map((q) => <li key={q}><button type="button" className="rounded-md border border-line-strong bg-surface px-2 py-1 text-left text-xs hover:bg-accent-soft" onClick={() => setValue('question', q, { shouldValidate: true })}>{q}</button></li>)}</ul></div>
      </Card>
      <Card className="space-y-4"><h2 className="font-semibold">Options</h2>
        <div className="flex items-start gap-3"><Switch label="Allow web search" checked={web} onCheckedChange={setWeb} />
          <div><p className="text-sm font-medium">Allow web search</p><p className="text-sm text-muted">Web queries leave your network: only the text of each research step is sent to the search provider, with personal data removed first.</p></div></div>
        <div className="flex items-start gap-3"><Switch label="Use memory" checked={memory} onCheckedChange={setMemory} />
          <div><p className="text-sm font-medium">Use memory</p><p className="text-sm text-muted">Recall summaries of your past investigations and save a summary of this one.</p></div></div>
        <Select label="Maximum improvement loops" value={loops} onChange={(e) => setLoops(e.target.value)} options={[1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: `${n} ${n === 1 ? 'loop' : 'loops'}` }))} />
        <fieldset><legend className="text-sm font-medium">Document scope</legend><p className="mb-2 text-sm text-muted">{scoped.length ? `${scoped.length} selected` : 'All ready documents are searched.'}</p>
          {docs.isError ? <p className="text-sm text-danger">Documents could not be loaded. All documents will be used.</p> : (
            <div className="grid max-h-40 gap-1 overflow-y-auto sm:grid-cols-2">{docs.data?.items.map((d) => <Checkbox key={d.id} label={d.title} checked={scoped.includes(d.id)} onChange={(e) => toggleDoc(d.id, e.target.checked)} />)}</div>)}</fieldset>
      </Card>
      <Button type="submit" disabled={!isValid} loading={start.isPending}>Start investigation</Button>
    </form>
  )
}
