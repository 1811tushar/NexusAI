import { expect, test } from '@playwright/test'
import { login } from './helpers'

test('analyst uploads a document and watches ingestion finish', async ({ page }) => {
  await login(page, 'analyst@nexus.test')
  await page.getByRole('link', { name: 'Documents' }).click()
  await page.locator('input[type=file]').setInputFiles({ name: 'board-notes.txt', mimeType: 'text/plain', buffer: Buffer.from('Revenue fell in the North.') })
  await expect(page.getByText('Uploaded. Ingestion has started.')).toBeVisible()
  const row = page.getByRole('row', { name: /board-notes/ })
  await expect(row).toBeVisible()
  await expect(row.getByText('Ready')).toBeVisible({ timeout: 12_000 })
})

test('a failed ingestion shows the reason and can be reindexed', async ({ page }) => {
  await login(page, 'analyst@nexus.test')
  await page.getByRole('link', { name: 'Documents' }).click()
  await page.locator('input[type=file]').setInputFiles({ name: 'bad-scan.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') })
  const row = page.getByRole('row', { name: /bad-scan/ })
  await expect(row.getByText(/could not be read/)).toBeVisible({ timeout: 12_000 })
  await row.getByRole('button', { name: 'Reindex' }).click()
  await expect(row.getByText('Ready')).toBeVisible({ timeout: 12_000 })
})

test('approver has read-only access to documents', async ({ page }) => {
  await login(page, 'approver@nexus.test')
  await page.getByRole('link', { name: 'Documents' }).click()
  await expect(page.getByText(/Your role can read and search documents/)).toBeVisible()
  await expect(page.getByRole('region', { name: 'Upload documents' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^Delete / })).toHaveCount(0)
})
