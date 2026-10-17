import type { ComponentType } from 'react'
import { BarChart3, Brain, CheckSquare, FileText, History, LayoutDashboard, ScrollText, Search, Settings, Users } from 'lucide-react'
import type { Role } from '@/common/types/api'

export interface NavItem { to: string; label: string; icon: ComponentType<{ className?: string }>; roles?: Role[]; badge?: boolean; inRail: boolean }
export const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, inRail: true },
  { to: '/investigate', label: 'Investigate', icon: Search, roles: ['ADMIN', 'ANALYST'], inRail: true },
  { to: '/history', label: 'History', icon: History, inRail: true },
  { to: '/approvals', label: 'Approvals', icon: CheckSquare, badge: true, inRail: true },
  { to: '/documents', label: 'Documents', icon: FileText, inRail: true },
  { to: '/memory', label: 'Memory', icon: Brain, inRail: true },
  { to: '/admin/evaluation', label: 'Evaluation', icon: BarChart3, roles: ['ADMIN'], inRail: true },
  { to: '/admin/users', label: 'Users', icon: Users, roles: ['ADMIN'], inRail: true },
  { to: '/admin/actions', label: 'Audit', icon: ScrollText, roles: ['ADMIN'], inRail: true },
  { to: '/settings', label: 'Settings', icon: Settings, inRail: false },
]
export const itemsFor = (role: Role) => navItems.filter((i) => !i.roles || i.roles.includes(role))
