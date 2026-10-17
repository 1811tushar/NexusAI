import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { http } from '@/common/api/httpClient'
import { toast } from '@/common/components/ui/toastStore'
import { useAuthStore } from '@/features/auth/authStore'

/** Polls every 60 s (FE-SH-07). Approvers and admins get a toast when the count goes up. */
export function usePendingApprovals(): number {
  const role = useAuthStore((s) => s.user?.role)
  const { data } = useQuery({
    queryKey: ['approvals', 'pending-count'],
    queryFn: () => http.get<{ count: number }>('/approvals/pending-count'),
    refetchInterval: 60_000,
    enabled: !!role,
  })
  const prev = useRef<number | null>(null)
  useEffect(() => {
    if (data === undefined) return
    if (prev.current !== null && data.count > prev.current && (role === 'APPROVER' || role === 'ADMIN')) toast.info('A new approval is waiting', 'Open Approvals to review it.')
    prev.current = data.count
  }, [data, role])
  return data?.count ?? 0
}
