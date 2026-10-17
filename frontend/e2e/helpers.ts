import { expect, type Page } from '@playwright/test'

export const REAL = !!process.env.E2E_BASE_URL
export const PASSWORD = process.env.E2E_PASSWORD ?? 'Passw0rd!!'
export const HERO = 'Why did Q2 revenue decline compared to Q1, and what should management investigate?'

/** Full-page login. Fine for single-user specs; multi-user specs use signIn/signOut so the in-page mock state survives. */
export async function login(page: Page, email: string) {
  await page.goto('/login')
  await signIn(page, email)
}
export async function signIn(page: Page, email: string) {
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL('/')
}
export async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Open user menu' }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login/)
}
/** Speeds up the mock agent run. No effect against the real stack. */
export const speedUp = (page: Page) => page.addInitScript(() => { window.__NX_SPEED__ = 0.2 })
export async function ask(page: Page, question: string) {
  await page.getByRole('link', { name: 'Investigate' }).click()
  await page.getByLabel('Your question').fill(question)
  await page.getByRole('button', { name: 'Start investigation' }).click()
  await expect(page).toHaveURL(/\/investigations\/\d+/)
}
declare global { interface Window { __NX_SPEED__?: number } }
