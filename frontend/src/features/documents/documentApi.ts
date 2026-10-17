import { API_BASE, http, refreshSession, tokenStore } from '@/common/api/httpClient'
import { ApiError } from '@/common/api/errors'
import type { ApiResponse, ChunkDTO, DocumentDTO, DocumentStatus, PagedResponse, SearchMode, SearchResultDTO, SourceType } from '@/common/types/api'

export interface DocumentQuery { q?: string; status?: DocumentStatus | ''; sourceType?: SourceType | ''; page?: number; size?: number }

/** Uses XHR (not fetch) because only XHR reports upload progress. Same auth + one refresh-retry as httpClient. */
export function uploadDocument(file: File, onProgress: (pct: number) => void): Promise<DocumentDTO> {
  const attempt = () => new Promise<{ status: number; body: ApiResponse<DocumentDTO> | null }>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/documents`)
    xhr.withCredentials = true
    const t = tokenStore.get()
    if (t) xhr.setRequestHeader('Authorization', `Bearer ${t}`)
    xhr.setRequestHeader('X-Request-Id', crypto.randomUUID())
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress((e.loaded / e.total) * 100) }
    xhr.onload = () => {
      let body: ApiResponse<DocumentDTO> | null = null
      try { body = JSON.parse(xhr.responseText) as ApiResponse<DocumentDTO> } catch { /* non-JSON */ }
      resolve({ status: xhr.status, body })
    }
    xhr.onerror = () => reject(new ApiError('NETWORK_ERROR', 'Cannot reach the server. Check your connection and try again.', 0))
    const fd = new FormData(); fd.append('file', file); xhr.send(fd)
  })
  return (async () => {
    let r = await attempt()
    if (r.status === 401 && (await refreshSession())) r = await attempt()
    if (r.status < 300 && r.body?.success && r.body.data) return r.body.data
    const e = r.body?.error
    throw new ApiError(e?.code ?? 'INTERNAL_ERROR', e?.message ?? 'Upload failed.', r.status, e?.details, e?.requestId)
  })()
}

async function fileBlob(id: number): Promise<Blob> {
  const t = tokenStore.get()
  const res = await fetch(`${API_BASE}/documents/${id}/file`, { credentials: 'include', headers: t ? { Authorization: `Bearer ${t}` } : {} })
  if (!res.ok) throw new ApiError('INTERNAL_ERROR', 'The original file could not be loaded.', res.status)
  return res.blob()
}

export const documentApi = {
  file: fileBlob,
  list: (p: DocumentQuery) => http.get<PagedResponse<DocumentDTO>>('/documents', { ...p }),
  get: (id: number) => http.get<DocumentDTO>(`/documents/${id}`),
  chunks: (id: number, page = 0, size = 100) => http.get<PagedResponse<ChunkDTO>>(`/documents/${id}/chunks`, { page, size }),
  reindex: (id: number) => http.post<DocumentDTO>(`/documents/${id}/reindex`),
  remove: (id: number) => http.del<void>(`/documents/${id}`),
  search: (q: string, mode: SearchMode, k = 8) => http.get<SearchResultDTO[]>('/search', { q, mode, k }),
  upload: uploadDocument,
}
