import { expect, test } from '@playwright/test'
import { ask, HERO, login } from './helpers'

// Runs against the mock layer AND the real stack (E2E_BASE_URL). It asserts only what the contract guarantees, not LLM wording.
test('analyst asks the hero question and the run reaches a pause or a report', async ({ page }) => {
  await login(page, process.env.E2E_ANALYST_EMAIL ?? 'analyst@nexus.test')
  await ask(page, HERO)
  await expect(page.getByRole('region', { name: 'Agent activity timeline' })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Waiting for approval|Executive summary|The investigation could not finish/ }).first()).toBeVisible({ timeout: REAL_WAIT })
})
const REAL_WAIT = process.env.E2E_BASE_URL ? 180_000 : 30_000
