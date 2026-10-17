import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { Role } from '@/common/types/api'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { useAuthStore } from './authStore'

export function ForbiddenPage() {
  return (
    <div className="mx-auto mt-16 max-w-md text-center">
      <h1 className="text-2xl font-semibold">You do not have access to this page</h1>
      <p className="mt-2 text-muted">Your role does not include this area. Ask an administrator if you need it.</p>
    </div>
  )
}

/** Restores session silently, redirects to /login with a return path, gates by role (renders 403 view). */
export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { user, restored, restore } = useAuthStore()
  const loc = useLocation()
  useEffect(() => { void restore() }, [restore])
  if (!restored) return <div className="p-8"><Skeleton className="h-8 w-48" /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />
  if (roles && !roles.includes(user.role)) return <ForbiddenPage />
  return <Outlet />
}
