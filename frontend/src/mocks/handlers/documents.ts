import { http, HttpResponse } from 'msw'
import type { DocumentDTO, SearchMode, SearchResultDTO, SourceType } from '@/common/types/api'
import { advance, chunkId, chunksOf, documents, markStarted } from '../db'
import { makePdf } from '../pdf'
import { fail, ok, paged } from '../util'
import { currentUser } from './auth'

const MAX = 20 * 1024 * 1024
const typeOf = (name: string): SourceType | null => {
  const e = name.split('.').pop()?.toUpperCase()
  return e === 'PDF' || e === 'DOCX' || e === 'TXT' || e === 'MD' ? e : null
}
const canManage = (d: DocumentDTO) => { const u = currentUser(); return !!u && (u.role === 'ADMIN' || (u.role === 'ANALYST' && d.uploadedBy.id === u.id)) }

export const documentHandlers = [
  http.get('/api/documents', ({ request }) => {
    const url = new URL(request.url); const q = (url.searchParams.get('q') ?? '').toLowerCase()
    const status = url.searchParams.get('status'); const st = url.searchParams.get('sourceType')
    const all = documents.map(advance).filter((d) => (!q || d.title.toLowerCase().includes(q) || d.originalFilename.toLowerCase().includes(q)) && (!status || d.status === status) && (!st || d.sourceType === st))
    return ok(paged([...all].sort((a, b) => b.createdAt.localeCompare(a.createdAt)), url))
  }),
  http.post('/api/documents', async ({ request }) => {
    const u = currentUser()
    if (!u || u.role === 'APPROVER') return fail('FORBIDDEN', 'Your role cannot upload documents.')
    const file = (await request.formData()).get('file')
    if (!(file instanceof File)) return fail('VALIDATION_FAILED', 'No file was sent.')
    const sourceType = typeOf(file.name)
    if (!sourceType) return fail('UNSUPPORTED_FILE_TYPE', 'Only PDF, DOCX, TXT and MD files are supported.')
    if (file.size > MAX) return fail('FILE_TOO_LARGE', 'Files must be 20 MB or smaller.')
    const dup = documents.find((d) => d.originalFilename === file.name)
    if (dup) return fail('DUPLICATE_RESOURCE', 'This document is already in the library.', { existingDocumentId: String(dup.id) })
    const doc: DocumentDTO = {
      id: Math.max(...documents.map((d) => d.id)) + 1, title: file.name.replace(/\.[^.]+$/, ''), originalFilename: file.name, sourceType,
      mimeType: file.type || 'application/octet-stream', sizeBytes: file.size, status: 'UPLOADED', errorMessage: null, pageCount: null, chunkCount: null,
      uploadedBy: { id: u.id, displayName: u.displayName }, createdAt: new Date().toISOString(), ingestedAt: null,
    }
    documents.push(doc); markStarted(doc.id)
    return ok(doc, 202)
  }),
  http.get('/api/documents/:id', ({ params }) => {
    const d = documents.find((x) => x.id === Number(params.id)); return d ? ok(advance(d)) : fail('NOT_FOUND', 'Document not found.')
  }),
  http.get('/api/documents/:id/file', ({ params }) => {
    const d = documents.find((x) => x.id === Number(params.id)); if (!d) return fail('NOT_FOUND', 'Document not found.')
    if (d.sourceType === 'PDF') return new HttpResponse(makePdf(d.pageCount ?? 3, d.title), { headers: { 'Content-Type': 'application/pdf' } })
    return new HttpResponse(chunksOf(d).map((c) => c.content).join('\n\n'), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } })
  }),
  http.get('/api/documents/:id/chunks', ({ params, request }) => {
    const d = documents.find((x) => x.id === Number(params.id)); if (!d) return fail('NOT_FOUND', 'Document not found.')
    return ok(paged(chunksOf(advance(d)), new URL(request.url)))
  }),
  http.post('/api/documents/:id/reindex', ({ params }) => {
    const d = documents.find((x) => x.id === Number(params.id)); if (!d) return fail('NOT_FOUND', 'Document not found.')
    if (!canManage(d)) return fail('FORBIDDEN', 'Only the uploader or an administrator can reindex this document.')
    d.status = 'UPLOADED'; d.errorMessage = null
    // A reindexed "bad" file gets a clean name so the demo can show recovery.
    d.originalFilename = d.originalFilename.replace(/bad|corrupt|encrypted/i, 'fixed'); markStarted(d.id)
    return ok(d, 202)
  }),
  http.delete('/api/documents/:id', ({ params }) => {
    const i = documents.findIndex((x) => x.id === Number(params.id)); const d = documents[i]
    if (!d) return fail('NOT_FOUND', 'Document not found.')
    if (!canManage(d)) return fail('FORBIDDEN', 'Only the uploader or an administrator can delete this document.')
    documents.splice(i, 1)
    return new Response(null, { status: 204 })
  }),
  http.get('/api/search', ({ request }) => {
    const url = new URL(request.url); const q = (url.searchParams.get('q') ?? '').toLowerCase()
    const k = Number(url.searchParams.get('k') ?? 8); const _mode = (url.searchParams.get('mode') ?? 'HYBRID') as SearchMode; void _mode
    const terms = q.split(/\s+/).filter((t) => t.length > 1)
    const out: SearchResultDTO[] = []
    for (const d of documents.filter((x) => x.status === 'READY')) {
      for (const c of chunksOf(d)) {
        const hits = terms.filter((t) => c.content.toLowerCase().includes(t)).length
        if (terms.length && hits) out.push({ chunkId: chunkId(d.id, c.chunkIndex), documentId: d.id, documentTitle: d.title, page: c.page, section: c.section, snippet: c.content, score: Math.min(1, hits / terms.length) })
      }
    }
    return ok(out.sort((a, b) => b.score - a.score).slice(0, k))
  }),
]
