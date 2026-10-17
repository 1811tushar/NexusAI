import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import type { Role, UserDTO } from '@/common/types/api'
import { ProtectedRoute } from './ProtectedRoute'
import { useAuthStore } from './authStore'

const user = (role: Role): UserDTO => ({ id: 1, email: 'a@b.c', displayName: 'A', role, enabled: true, createdAt: '' })
const renderAt = () => render(
  <MemoryRouter initialEntries={['/admin']}>
    <Routes>
      <Route path="/login" element={<div>login screen</div>} />
      <Route element={<ProtectedRoute roles={['ADMIN']} />}><Route path="/admin" element={<div>admin area</div>} /></Route>
    </Routes>
  </MemoryRouter>)

describe('role gating', () => {
  beforeEach(() => useAuthStore.setState({ user: null, restored: true }))
  it('redirects anonymous users to login', () => { renderAt(); expect(screen.getByText('login screen')).toBeInTheDocument() })
  it('shows the 403 view to a role without access', () => {
    useAuthStore.setState({ user: user('APPROVER'), restored: true }); renderAt()
    expect(screen.getByText(/do not have access/i)).toBeInTheDocument(); expect(screen.queryByText('admin area')).toBeNull()
  })
  it('lets the allowed role through', () => { useAuthStore.setState({ user: user('ADMIN'), restored: true }); renderAt(); expect(screen.getByText('admin area')).toBeInTheDocument() })
})
