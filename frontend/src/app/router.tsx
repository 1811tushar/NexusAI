import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router-dom'
import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from './AppShell'
import { ForbiddenPage, ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'

const NotFound = () => <div className="mx-auto mt-16 max-w-md text-center"><h1 className="text-2xl font-semibold">Page not found</h1><p className="mt-2 text-muted">Check the address or use the navigation.</p></div>
// Route-level code splitting (FE-PF-01).
const lazyPage = <T extends Record<string, unknown>>(load: () => Promise<T>, key: keyof T): RouteObject['lazy'] =>
  async () => ({ Component: (await load())[key] as ComponentType })

const devRoutes: RouteObject[] = import.meta.env.DEV ? [{ path: '/dev/ui', lazy: lazyPage(() => import('@/dev/DevUi'), 'DevUi') }] : []

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  ...devRoutes,
  {
    element: <ProtectedRoute />,
    children: [{
      element: <AppShell />,
      children: [
        { path: '/', lazy: lazyPage(() => import('@/features/dashboard/DashboardPage'), 'DashboardPage') },
        { path: '/documents', lazy: lazyPage(() => import('@/features/documents/DocumentsPage'), 'DocumentsPage') },
        { path: '/documents/:id', lazy: lazyPage(() => import('@/features/documents/DocumentViewerPage'), 'DocumentViewerPage') },
        { path: '/memory', lazy: lazyPage(() => import('@/features/memory/MemoryPage'), 'MemoryPage') },
        { path: '/settings', lazy: lazyPage(() => import('@/features/settings/SettingsPage'), 'SettingsPage') },
        // Owned by Frontend B: replace each element, keep path and role gate.
        { path: '/history', lazy: lazyPage(() => import('@/features/history/HistoryPage'), 'HistoryPage') },
        { path: '/approvals', lazy: lazyPage(() => import('@/features/approvals/ApprovalsPage'), 'ApprovalsPage') },
        { path: '/approvals/:id', lazy: lazyPage(() => import('@/features/approvals/ApprovalDetailPage'), 'ApprovalDetailPage') },
        { path: '/investigations/:id', lazy: lazyPage(() => import('@/features/investigations/InvestigationPage'), 'InvestigationPage') },
        { element: <ProtectedRoute roles={['ADMIN', 'ANALYST']} />, children: [{ path: '/investigate', lazy: lazyPage(() => import('@/features/investigations/InvestigatePage'), 'InvestigatePage') }] },
        {
          element: <ProtectedRoute roles={['ADMIN']} />,
          children: [
            { path: '/admin/users', lazy: lazyPage(() => import('@/features/admin/UsersPage'), 'UsersPage') },
            { path: '/admin/evaluation', lazy: lazyPage(() => import('@/features/evaluation/EvalDashboard'), 'EvalDashboard') },
            { path: '/admin/actions', lazy: lazyPage(() => import('@/features/admin/ActionLogPage'), 'ActionLogPage') },
          ],
        },
        { path: '/403', element: <ForbiddenPage /> },
        { path: '*', element: <NotFound /> },
      ],
    }],
  },
])
