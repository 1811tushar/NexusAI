import { keepPreviousData, useQuery } from '@tanstack/react-query'
import type { ApprovalStatus } from '@/common/types/api'
import { approvalApi } from './approvalApi'
export const useApprovals = (status: ApprovalStatus | '', page: number) =>
  useQuery({ queryKey: ['approvals', 'list', status, page], queryFn: () => approvalApi.list({ status, page, size: 10 }), placeholderData: keepPreviousData })
