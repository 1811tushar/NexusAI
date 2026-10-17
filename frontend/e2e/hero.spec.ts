import { expect, test } from '@playwright/test'
import { ask, HERO, REAL, signIn, signOut, speedUp } from './helpers'

test.skip(REAL, 'Mock-scenario assertions (loop, two high-risk actions). Use real-smoke.spec.ts against the real stack.')

test('hero scenario: upload, ask, watch the run, approver decides, analyst sees the executed (simulated) action', async ({ page }) => {
  await speedUp(page)
  await page.goto('/login')
  await signIn(page, 'analyst@nexus.test')

  // upload a document
  await page.getByRole('link', { name: 'Documents' }).click()
  await page.locator('input[type=file]').setInputFiles({ name: 'q2-notes.txt', mimeType: 'text/plain', buffer: Buffer.from('Northern shipments were delayed.') })
  await expect(page.getByText('Uploaded. Ingestion has started.')).toBeVisible()

  // ask the hero question and watch plan, tools, evidence, claims, loop
  await ask(page, HERO)
  await expect(page.getByRole('region', { name: 'Agent activity timeline' })).toBeVisible()
  await expect(page.getByText('Plan ready with 4 steps').first()).toBeVisible()
  await expect(page.getByText(/used SQL query/).first()).toBeVisible()
  await expect(page.getByText(/Evidence added: Revenue by region/).first()).toBeVisible()
  await expect(page.getByText('Unsupported', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/Looping back 1 of 3/).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Waiting for approval' })).toBeVisible()
  await expect(page.getByText('Read-only for your role')).toBeVisible()

  // approver approves both high-risk actions
  await signOut(page)
  await signIn(page, 'approver@nexus.test')
  await page.getByRole('link', { name: /Approvals/ }).click()
  for (let i = 0; i < 2; i++) {
    const before = await page.getByRole('article').count()
    await page.getByRole('button', { name: 'Review and decide' }).first().click()
    await page.getByLabel('Approve', { exact: true }).check()
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page.getByText(/simulated execution/i)).toBeVisible()
    await page.getByRole('button', { name: 'Confirm approval' }).click()
    await expect(page.getByText('Approved. Execution is simulated.')).toBeVisible()
    await expect(page.getByRole('article')).toHaveCount(before - 1)
  }

  // analyst sees the completed report with the executed (simulated) actions
  await signOut(page)
  await signIn(page, 'analyst@nexus.test')
  await page.getByRole('link', { name: 'History' }).click()
  await page.getByRole('link', { name: HERO }).first().click()
  await expect(page.getByRole('heading', { name: 'Executive summary' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Executed (simulated)').first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Decisions on proposed actions' })).toBeVisible()

  // claims, evidence drawer, trace
  await page.getByRole('tab', { name: /Claims/ }).click()
  await page.getByRole('button', { name: 'Unsupported (1)' }).click()
  await expect(page.getByText('A competitor discount bundle caused lost share.')).toBeVisible()
  await page.getByRole('button', { name: 'All (5)' }).click()
  await page.getByRole('button', { name: /^Source 1/ }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('tab', { name: 'Trace' }).click()
  await expect(page.getByRole('region', { name: 'Agent activity timeline' })).toBeVisible()
})
