import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { login, REAL } from './helpers'

const serious = async (page: Page) =>
  (await new AxeBuilder({ page }).analyze()).violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
const open = async (page: Page, path: string, ready: RegExp | string) => {
  await page.goto(path); await expect(page.getByRole('heading', { name: ready }).first()).toBeVisible()
}

test('login and register pages have no serious or critical axe violations', async ({ page }) => {
  for (const p of ['/login', '/register']) { await page.goto(p); expect(await serious(page), p).toEqual([]) }
})
test('every analyst page has no serious or critical axe violations (light and dark)', async ({ page }) => {
  test.skip(REAL, 'Uses mock data for stable content')
  await login(page, 'analyst@nexus.test')
  const pages: [string, RegExp | string][] = [['/', /Welcome/], ['/documents', 'Documents'], ['/documents/1', /Quarterly Report/], ['/history', 'History'], ['/approvals', 'Approvals'], ['/memory', 'Memory'], ['/settings', 'Settings'], ['/investigate', 'Investigate']]
  for (const theme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: theme as 'light' | 'dark' })
    for (const [path, ready] of pages) { await open(page, path, ready); expect(await serious(page), `${theme} ${path}`).toEqual([]) }
  }
})
test('admin pages have no serious or critical axe violations', async ({ page }) => {
  test.skip(REAL, 'Uses mock data for stable content')
  await login(page, 'admin@nexus.test')
  for (const [path, ready] of [['/admin/users', 'Users'], ['/admin/actions', 'Action log'], ['/admin/evaluation', 'Evaluation']] as [string, string][]) { await open(page, path, ready); expect(await serious(page), path).toEqual([]) }
})
