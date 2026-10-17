import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/common/api/errors'
import type { DocumentDTO } from '@/common/types/api'
import { UploadZone } from './UploadZone'

const file = (name: string, size?: number) => {
  const f = new File(['content'], name)
  if (size !== undefined) Object.defineProperty(f, 'size', { value: size })
  return f
}
const setup = (upload = vi.fn().mockResolvedValue({ id: 1 } as DocumentDTO)) => {
  const user = userEvent.setup({ applyAccept: false })
  render(<UploadZone upload={upload} />)
  return { user, upload, input: screen.getByLabelText(/choose files/i) }
}

describe('UploadZone', () => {
  it('uploads a valid file and reports success', async () => {
    const { user, upload, input } = setup()
    await user.upload(input, file('report.pdf'))
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/Ingestion has started/)).toBeInTheDocument()
  })
  it('rejects an unsupported type on the client without calling the server', async () => {
    const { user, upload, input } = setup()
    await user.upload(input, file('malware.exe'))
    expect(await screen.findByText(/Unsupported type/)).toBeInTheDocument()
    expect(upload).not.toHaveBeenCalled()
  })
  it('rejects files over 20 MB', async () => {
    const { user, upload, input } = setup()
    await user.upload(input, file('huge.pdf', 21 * 1024 * 1024))
    expect(await screen.findByText(/Too large/)).toBeInTheDocument()
    expect(upload).not.toHaveBeenCalled()
  })
  it('shows the server message when an upload fails (duplicate)', async () => {
    const { user, input } = setup(vi.fn().mockRejectedValue(new ApiError('DUPLICATE_RESOURCE', 'This document is already in the library.', 409)))
    await user.upload(input, file('dup.txt'))
    expect(await screen.findByText('This document is already in the library.')).toBeInTheDocument()
  })
})
