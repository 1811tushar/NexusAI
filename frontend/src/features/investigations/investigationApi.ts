import { API_BASE, http, tokenStore } from '@/common/api/httpClient'
import { ApiError } from '@/common/api/errors'
import type { InvestigationDTO, InvestigationStatus, PagedResponse } from '@/common/types/api'
import type { AgentStepDTO, InvestigationDetailDTO, StartInvestigationRequest } from './types'

export interface InvestigationQuery { status?: InvestigationStatus | ''; q?: string; mine?: boolean; page?: number; size?: number; sort?: string }
export const investigationApi = {
  start: (b: StartInvestigationRequest) => http.post<InvestigationDTO>('/investigations', b),
  list: (p: InvestigationQuery) => http.get<PagedResponse<InvestigationDTO>>('/investigations', { ...p }),
  get: (id: number) => http.get<InvestigationDetailDTO>(`/investigations/${id}`),
  steps: (id: number) => http.get<AgentStepDTO[]>(`/investigations/${id}/steps`),
  cancel: (id: number) => http.post<void>(`/investigations/${id}/cancel`),
  feedback: (id: number, b: { rating: 1 | -1; comment?: string }) => http.post<null>(`/investigations/${id}/feedback`, b),
  /** Stream path; `after` makes the server replay only events newer than what we already hold. */
  streamPath: (id: number, after: number) => `/investigations/${id}/stream?after=${after}`,
  /** report.md is a file download (exempt from the envelope). */
  async exportMarkdown(id: number): Promise<Blob> {
    const t = tokenStore.get()
    const res = await fetch(`${API_BASE}/investigations/${id}/report.md`, { credentials: 'include', headers: t ? { Authorization: `Bearer ${t}` } : {} })
    if (!res.ok) throw new ApiError('INTERNAL_ERROR', 'The report could not be exported.', res.status)
    return res.blob()
  },
}
