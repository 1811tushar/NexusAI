import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/common/api/errors'
import { LoginPage } from './LoginPage'
import { authApi } from './authApi'

vi.mock('./authApi', () => ({ authApi: { login: vi.fn() } }))
const setup = () => { render(<MemoryRouter><LoginPage /></MemoryRouter>); return userEvent.setup() }

describe('LoginPage', () => {
  it('keeps Sign in disabled until the form is valid', async () => {
    const user = setup()
    const btn = screen.getByRole('button', { name: 'Sign in' })
    expect(btn).toBeDisabled()
    await user.type(screen.getByLabelText('Email'), 'ada@nexus.test')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await waitFor(() => expect(btn).toBeEnabled())
  })
  it('shows an inline email error for invalid input', async () => {
    const user = setup()
    await user.type(screen.getByLabelText('Email'), 'nope')
    await user.tab()
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
  })
  it('shows the server error message on failed sign-in', async () => {
    vi.mocked(authApi.login).mockRejectedValue(new ApiError('INVALID_CREDENTIALS', 'Email or password is incorrect.', 401))
    const user = setup()
    await user.type(screen.getByLabelText('Email'), 'ada@nexus.test')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.')
  })
})
