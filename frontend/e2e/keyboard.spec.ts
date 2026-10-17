import { expect, test } from '@playwright/test'
import { login, REAL } from './helpers'

test.skip(REAL, 'Mock-only')
test('command palette opens with Ctrl+K, filters, and Enter navigates', async ({ page }) => {
  await login(page, 'analyst@nexus.test')
  await page.keyboard.press('Control+k')
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.type('Mem'); await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/memory/)
})
test('decision dialog is operable by keyboard, Escape closes it and focus returns to the trigger', async ({ page }) => {
  await login(page, 'approver@nexus.test')
  await page.getByRole('link', { name: /Approvals/ }).click()
  const trigger = page.getByRole('button', { name: 'Review and decide' }).first()
  await trigger.focus(); await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden(); await expect(trigger).toBeFocused()
})
test('the agent timeline is a focusable, labelled region', async ({ page }) => {
  await login(page, 'analyst@nexus.test')
  await page.getByRole('link', { name: 'History' }).click(); await page.getByRole('link', { name: /Which region grew/ }).click()
  await page.getByRole('tab', { name: 'Trace' }).click()
  const region = page.getByRole('region', { name: 'Agent activity timeline' }); await region.focus(); await expect(region).toBeFocused()
})
test('the cited PDF page can be opened from the document viewer', async ({ page }) => {
  await login(page, 'analyst@nexus.test')
  await page.goto('/documents/1')
  await page.getByRole('button', { name: /View original PDF at page/ }).click()
  await expect(page.locator('iframe[title^="Original PDF"]')).toBeVisible()
})
