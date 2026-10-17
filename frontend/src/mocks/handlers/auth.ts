import { http } from 'msw'
import type { Role, UserDTO } from '@/common/types/api'
import { fail, mockSession, ok, paged, stripPassword, type MockUser } from '../util'

const mk = (id: number, email: string, displayName: string, role: Role): MockUser =>
  ({ id, email, displayName, role, enabled: true, createdAt: '2026-01-01T00:00:00Z', password: 'Passw0rd!!' })
export const mockUsers: MockUser[] = [
  mk(1, 'analyst@nexus.test', 'Ada Analyst', 'ANALYST'),
  mk(2, 'approver@nexus.test', 'Ravi Approver', 'APPROVER'),
  mk(3, 'admin@nexus.test', 'Alex Admin', 'ADMIN'),
]
export const currentUser = (): MockUser | undefined => mockUsers.find((u) => u.id === mockSession.get() && u.enabled)
const session = (u: UserDTO) => ({ accessToken: `mock-${u.id}-${Date.now()}`, expiresInSeconds: 900, user: u })
const strongEnough = (p: string) => p.length >= 10 && /[A-Za-z]/.test(p) && /\d/.test(p)
// Flip to false to preview the "registration closed" state.
const REGISTRATION_OPEN = true

export const authHandlers = [
  http.post('/api/auth/login', async ({ request }) => {
    const b = (await request.json()) as { email: string; password: string }
    const u = mockUsers.find((x) => x.email === b.email && x.password === b.password)
    if (!u || !u.enabled) return fail('INVALID_CREDENTIALS', 'Email or password is incorrect.')
    mockSession.set(u.id)
    return ok(session(stripPassword(u)))
  }),
  http.post('/api/auth/register', async ({ request }) => {
    if (!REGISTRATION_OPEN) return fail('FORBIDDEN', 'Registration is closed. Ask an administrator to create your account.')
    const b = (await request.json()) as { email: string; password: string; displayName: string }
    if (!strongEnough(b.password)) return fail('VALIDATION_FAILED', 'Check the highlighted fields.', { password: 'Use at least 10 characters with a letter and a digit.' })
    if (mockUsers.some((u) => u.email === b.email)) return fail('DUPLICATE_RESOURCE', 'An account with this email already exists.', { email: 'Already registered.' })
    const u = mk(Math.max(...mockUsers.map((x) => x.id)) + 1, b.email, b.displayName, 'ANALYST')
    u.password = b.password; mockUsers.push(u); mockSession.set(u.id)
    return ok(session(stripPassword(u)), 201)
  }),
  http.post('/api/auth/refresh', () => { const u = currentUser(); return u ? ok(session(stripPassword(u))) : fail('UNAUTHENTICATED', 'Signed out.') }),
  http.post('/api/auth/logout', () => { mockSession.set(null); return ok(null) }),
  http.get('/api/auth/me', () => { const u = currentUser(); return u ? ok(stripPassword(u)) : fail('UNAUTHENTICATED', 'Signed out.') }),
  http.patch('/api/users/me', async ({ request }) => {
    const u = currentUser(); if (!u) return fail('UNAUTHENTICATED', 'Signed out.')
    const b = (await request.json()) as { displayName: string }
    if (!b.displayName?.trim()) return fail('VALIDATION_FAILED', 'Check the highlighted fields.', { displayName: 'Enter a name.' })
    u.displayName = b.displayName.trim()
    return ok(stripPassword(u))
  }),
  http.post('/api/users/me/password', async ({ request }) => {
    const u = currentUser(); if (!u) return fail('UNAUTHENTICATED', 'Signed out.')
    const b = (await request.json()) as { currentPassword: string; newPassword: string }
    if (b.currentPassword !== u.password) return fail('INVALID_CREDENTIALS', 'Current password is incorrect.', { currentPassword: 'Incorrect password.' })
    if (!strongEnough(b.newPassword)) return fail('VALIDATION_FAILED', 'Check the highlighted fields.', { newPassword: 'Use at least 10 characters with a letter and a digit.' })
    u.password = b.newPassword
    return ok(null)
  }),
  // ADMIN user management (FE-AD-01) with the server-side guards the UI must surface.
  http.get('/api/admin/users', ({ request }) => {
    const me = currentUser(); if (me?.role !== 'ADMIN') return fail('FORBIDDEN', 'Administrators only.')
    const url = new URL(request.url); const q = (url.searchParams.get('q') ?? '').toLowerCase(); const role = url.searchParams.get('role')
    return ok(paged(mockUsers.filter((u) => (!q || u.email.includes(q) || u.displayName.toLowerCase().includes(q)) && (!role || u.role === role)).map(stripPassword), url))
  }),
  http.post('/api/admin/users', async ({ request }) => {
    const me = currentUser(); if (me?.role !== 'ADMIN') return fail('FORBIDDEN', 'Administrators only.')
    const b = (await request.json()) as { email: string; displayName: string; role: Role; temporaryPassword: string }
    if (mockUsers.some((u) => u.email === b.email)) return fail('DUPLICATE_RESOURCE', 'An account with this email already exists.', { email: 'Already registered.' })
    if (!strongEnough(b.temporaryPassword)) return fail('VALIDATION_FAILED', 'Check the highlighted fields.', { temporaryPassword: 'Use at least 10 characters with a letter and a digit.' })
    const u = mk(Math.max(...mockUsers.map((x) => x.id)) + 1, b.email, b.displayName, b.role); u.password = b.temporaryPassword; mockUsers.push(u)
    return ok(stripPassword(u), 201)
  }),
  http.patch('/api/admin/users/:id', async ({ request, params }) => {
    const me = currentUser(); if (me?.role !== 'ADMIN') return fail('FORBIDDEN', 'Administrators only.')
    const u = mockUsers.find((x) => x.id === Number(params.id)); if (!u) return fail('NOT_FOUND', 'User not found.')
    const b = (await request.json()) as { role?: Role; enabled?: boolean }
    const admins = mockUsers.filter((x) => x.role === 'ADMIN' && x.enabled).length
    const losesAdmin = u.role === 'ADMIN' && ((b.role && b.role !== 'ADMIN') || b.enabled === false)
    if (u.id === me.id && losesAdmin) return fail('INVALID_STATE', 'You cannot demote or disable your own account.')
    if (losesAdmin && admins <= 1) return fail('INVALID_STATE', 'This is the last active administrator. Promote another user first.')
    if (b.role) u.role = b.role
    if (b.enabled !== undefined) u.enabled = b.enabled
    return ok(stripPassword(u))
  }),
]
