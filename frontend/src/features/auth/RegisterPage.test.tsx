import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/common/api/errors'
import { RegisterPage } from './RegisterPage'
import { authApi } from './authApi'

vi.mock('./authApi', () => ({ authApi: { register: vi.fn() } }))
const fill = async (pw = 'Longenough1') => {
  const user = userEvent.setup(); render(<MemoryRouter><RegisterPage /></MemoryRouter>)
  await user.type(screen.getByLabelText('Name'), 'Ada'); await user.type(screen.getByLabelText('Email'), 'ada@x.test'); await user.type(screen.getByLabelText('Password'), pw)
  return user
}
describe('RegisterPage', () => {
  it('enforces the password policy (10+ characters, a letter, a digit) before enabling submit', async () => {
    await fill('short1'); expect(await screen.findByText('Use at least 10 characters')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create account' })).toBeDisabled()
  })
  it('enables submit for a valid form', async () => { await fill(); await waitFor(() => expect(screen.getByRole('button', { name: 'Create account' })).toBeEnabled()) })
  it('shows a calm "self sign-up is off" state when the server refuses registration', async () => {
    vi.mocked(authApi.register).mockRejectedValue(new ApiError('FORBIDDEN', 'closed', 403))
    const user = await fill(); await user.click(await screen.findByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Self sign-up is turned off')).toBeInTheDocument(); expect(screen.queryByLabelText('Email')).toBeNull()
  })
  it('maps server field errors (duplicate email) onto the field', async () => {
    vi.mocked(authApi.register).mockRejectedValue(new ApiError('DUPLICATE_RESOURCE', 'exists', 409, { email: 'Already registered.' }))
    const user = await fill(); await user.click(await screen.findByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Already registered.')).toBeInTheDocument()
  })
})
