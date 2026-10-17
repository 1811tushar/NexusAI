import { useQuery } from '@tanstack/react-query'
import { http } from '@/common/api/httpClient'
import type { DashboardSummaryDTO } from '@/common/types/api'
export const useDashboard = () => useQuery({ queryKey: ['dashboard'], queryFn: () => http.get<DashboardSummaryDTO>('/dashboard/summary') })
