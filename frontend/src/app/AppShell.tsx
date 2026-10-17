import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Activity, LogOut, Monitor, Moon, Settings, Sun } from 'lucide-react'
import { cn } from '@/common/utils/cn'
import { Avatar } from '@/common/components/ui/Avatar'
import { Badge } from '@/common/components/ui/Badge'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/common/components/ui/DropdownMenu'
import { NetworkBanner } from '@/common/components/NetworkBanner'
import { useTheme } from '@/common/theme/ThemeProvider'
import { useAuthStore } from '@/features/auth/authStore'
import { authApi } from '@/features/auth/authApi'
import type { Role } from '@/common/types/api'
import { CommandPalette } from './CommandPalette'
import { itemsFor } from './navItems'
import { usePendingApprovals } from './usePendingApprovals'
import { RunWatcher } from '@/features/investigations/runWatcher'

const roleLabel: Record<Role, string> = { ADMIN: 'Admin', ANALYST: 'Analyst', APPROVER: 'Approver' }

export function AppShell() {
  const user = useAuthStore((s) => s.user)
  const clear = useAuthStore((s) => s.clear)
  const nav = useNavigate()
  const { setTheme } = useTheme()
  const pending = usePendingApprovals()
  if (!user) return null
  const rail = itemsFor(user.role).filter((i) => i.inRail)

  return (
    <div className="min-h-screen md:grid md:grid-cols-[15rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:p-2">Skip to content</a>
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-20 flex overflow-x-auto border-t border-line bg-surface md:static md:flex-col md:gap-1 md:overflow-visible md:border-r md:border-t-0 md:p-3">
        <div className="hidden items-center gap-2 px-2 py-3 text-lg font-semibold md:flex"><Activity className="h-5 w-5 text-accent" aria-hidden />NexusAI</div>
        {rail.map(({ to, label, icon: Icon, badge }) => (
          <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) =>
            cn('flex min-w-16 flex-1 flex-col items-center gap-1 px-2 py-2 text-xs md:min-w-0 md:flex-none md:flex-row md:gap-3 md:rounded-md md:text-sm',
              isActive ? 'bg-accent-soft font-semibold text-accent' : 'text-muted hover:text-ink')}>
            <Icon className="h-4 w-4" aria-hidden /><span>{label}</span>
            {badge && pending > 0 && <Badge tone="warning" className="md:ml-auto"><span aria-label={`${pending} pending`}>{pending}</span></Badge>}
          </NavLink>
        ))}
      </nav>
      <div className="pb-16 md:pb-0">
        <NetworkBanner />
        <header className="flex items-center justify-end gap-3 border-b border-line bg-surface px-4 py-2">
          <Badge tone="accent">{roleLabel[user.role]}</Badge>
          <DropdownMenu>
            <DropdownMenuTrigger aria-label="Open user menu" className="flex items-center gap-2 rounded-md p-1 hover:bg-accent-soft">
              <Avatar name={user.displayName} /><span className="hidden text-sm sm:inline">{user.displayName}</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuLabel>{user.email}</DropdownMenuLabel>
              <DropdownMenuItem onSelect={() => nav('/settings')}><Settings className="h-4 w-4" aria-hidden />Settings</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Theme</DropdownMenuLabel>
              <DropdownMenuItem onSelect={() => setTheme('SYSTEM')}><Monitor className="h-4 w-4" aria-hidden />Match system</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setTheme('LIGHT')}><Sun className="h-4 w-4" aria-hidden />Light</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setTheme('DARK')}><Moon className="h-4 w-4" aria-hidden />Dark</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={async () => { await authApi.logout(); clear(); nav('/login') }}><LogOut className="h-4 w-4" aria-hidden />Sign out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>
        <main id="main" className="mx-auto max-w-6xl p-4 md:p-8"><Outlet /></main>
      </div>
      <CommandPalette />
      <RunWatcher />
    </div>
  )
}
