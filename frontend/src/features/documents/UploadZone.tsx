import { useId, useRef, useState, type DragEvent } from 'react'
import { CheckCircle2, UploadCloud, XCircle } from 'lucide-react'
import type { DocumentDTO } from '@/common/types/api'
import { isApiError } from '@/common/api/errors'
import { Progress } from '@/common/components/ui/Progress'
import { formatBytes } from '@/common/utils/format'
import { cn } from '@/common/utils/cn'
import { documentApi } from './documentApi'

export const MAX_BYTES = 20 * 1024 * 1024
export const ALLOWED = ['pdf', 'docx', 'txt', 'md']
export function validateFile(f: File): string | null {
  const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
  if (!ALLOWED.includes(ext)) return 'Unsupported type. Use PDF, DOCX, TXT or MD.'
  if (f.size > MAX_BYTES) return `Too large (${formatBytes(f.size)}). The limit is 20 MB.`
  if (f.size === 0) return 'The file is empty.'
  return null
}

interface Item { key: number; name: string; size: number; state: 'uploading' | 'done' | 'error'; progress: number; message: string }
interface Props { upload?: (f: File, onProgress: (pct: number) => void) => Promise<DocumentDTO>; onUploaded?: (d: DocumentDTO) => void }
let counter = 0

export function UploadZone({ upload = documentApi.upload, onUploaded }: Props) {
  const [items, setItems] = useState<Item[]>([])
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const id = useId()
  const patch = (key: number, p: Partial<Item>) => setItems((xs) => xs.map((x) => (x.key === key ? { ...x, ...p } : x)))

  const handle = (files: FileList | File[]) => {
    Array.from(files).forEach((f) => {
      const key = ++counter
      const bad = validateFile(f)
      setItems((xs) => [...xs, { key, name: f.name, size: f.size, state: bad ? 'error' : 'uploading', progress: 0, message: bad ?? 'Uploading' }])
      if (bad) return
      upload(f, (p) => patch(key, { progress: p }))
        .then((d) => { patch(key, { state: 'done', progress: 100, message: 'Uploaded. Ingestion has started.' }); onUploaded?.(d) })
        .catch((e: unknown) => patch(key, { state: 'error', message: isApiError(e) ? e.display : 'Upload failed.' }))
    })
    if (input.current) input.current.value = ''
  }
  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); handle(e.dataTransfer.files) }

  return (
    <section aria-label="Upload documents" className="space-y-3">
      <div onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={onDrop}
        className={cn('flex flex-col items-center gap-2 rounded-lg border-2 border-dashed p-6 text-center focus-within:ring-2 focus-within:ring-[var(--focus)]', over ? 'border-accent bg-accent-soft' : 'border-line-strong')}>
        <UploadCloud className="h-6 w-6 text-accent" aria-hidden />
        <p className="font-medium">Drop files here, or <label htmlFor={id} className="cursor-pointer text-accent underline">choose files</label></p>
        <p className="text-sm text-muted">PDF, DOCX, TXT or MD, up to 20 MB each</p>
        <input ref={input} id={id} type="file" multiple accept=".pdf,.docx,.txt,.md" className="sr-only" onChange={(e) => e.target.files && handle(e.target.files)} />
      </div>
      {items.length > 0 && (
        <ul className="space-y-2">
          {items.map((it) => (
            <li key={it.key} className="rounded-md border border-line bg-surface p-3 text-sm">
              <div className="flex items-center gap-2">
                {it.state === 'done' && <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />}
                {it.state === 'error' && <XCircle className="h-4 w-4 text-danger" aria-hidden />}
                <span className="flex-1 truncate font-medium">{it.name}</span><span className="text-muted">{formatBytes(it.size)}</span>
              </div>
              {it.state === 'uploading' ? <div className="mt-2"><Progress value={it.progress} label={`Uploading ${it.name}`} /></div>
                : <p className={cn('mt-1', it.state === 'error' ? 'text-danger' : 'text-muted')} role={it.state === 'error' ? 'alert' : undefined}>{it.message}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
