import './index.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/common/theme/ThemeProvider'
import { ErrorBoundary } from '@/common/components/ErrorBoundary'
import { Toaster } from '@/common/components/ui/Toaster'
import { router } from '@/app/router'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

async function boot() {
  if (import.meta.env.VITE_USE_MOCKS === 'true') {
    const { worker } = await import('@/mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ErrorBoundary><ThemeProvider><QueryClientProvider client={qc}><RouterProvider router={router} /><Toaster /></QueryClientProvider></ThemeProvider></ErrorBoundary>
    </StrictMode>,
  )
}
void boot()
