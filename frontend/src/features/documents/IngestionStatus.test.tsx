import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { DocumentDTO } from '@/common/types/api'
import { IngestionStatus } from './IngestionStatus'
import { hasInProgress } from './useDocuments'

const doc = (p: Partial<DocumentDTO>) => ({ id: 7, status: 'READY', errorMessage: null, ...p }) as DocumentDTO

describe('IngestionStatus', () => {
  it('FAILED shows the reason and lets an allowed user reindex', async () => {
    const onReindex = vi.fn()
    render(<IngestionStatus doc={doc({ status: 'FAILED', errorMessage: 'Encrypted PDF' })} canManage onReindex={onReindex} />)
    expect(screen.getByText('Encrypted PDF')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /reindex/i }))
    expect(onReindex).toHaveBeenCalledWith(7)
  })
  it('hides Reindex when the user cannot manage the document', () => {
    render(<IngestionStatus doc={doc({ status: 'FAILED', errorMessage: 'x' })} canManage={false} onReindex={() => {}} />)
    expect(screen.queryByRole('button', { name: /reindex/i })).toBeNull()
  })
  it('READY shows no error text or action', () => {
    render(<IngestionStatus doc={doc({})} canManage onReindex={() => {}} />)
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })
})

describe('polling rule', () => {
  it('polls only while a document is still being processed', () => {
    expect(hasInProgress([doc({ status: 'READY' }), doc({ status: 'FAILED' })])).toBe(false)
    expect(hasInProgress([doc({ status: 'READY' }), doc({ status: 'INGESTING' })])).toBe(true)
    expect(hasInProgress(undefined)).toBe(false)
  })
})
