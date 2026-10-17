import { http } from '@/common/api/httpClient'
import type { ApprovalStatus, PagedResponse } from '@/common/types/api'
import type { ActionLogDTO, ApprovalDTO } from '@/features/investigations/types'

export const approvalApi = {
  list: (p: { status?: ApprovalStatus | ''; page?: number; size?: number }) => http.get<PagedResponse<ApprovalDTO>>('/approvals', { ...p }),
  get: (id: number) => http.get<ApprovalDTO>(`/approvals/${id}`),
  decide: (id: number, b: { decision: 'APPROVE' | 'REJECT'; comment?: string }) => http.post<ApprovalDTO>(`/approvals/${id}/decision`, b),
  actions: (page = 0, size = 20) => http.get<PagedResponse<ActionLogDTO>>('/actions', { page, size }),
}
