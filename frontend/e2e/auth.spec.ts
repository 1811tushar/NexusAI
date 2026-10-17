import { expect, test } from '@playwright/test'
import { login } from './helpers'

test('analyst signs in and the nav matches the role', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/login/)
  await login(page, 'analyst@nexus.test')
  await expect(page.getByText('Analyst', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Users' })).toHaveCount(0)
})
test('admin sees admin navigation and the users page', async ({ page }) => {
  await login(page, 'admin@nexus.test')
  await page.getByRole('link', { name: 'Users' }).click()
  await expect(page.getByRole('table', { name: 'Users' })).toBeVisible()
})
test('wrong password shows an inline error', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill('analyst@nexus.test')
  await page.getByLabel('Password').fill('nope')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText('incorrect')
})
