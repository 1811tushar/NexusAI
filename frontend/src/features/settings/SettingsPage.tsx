import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import type { Role, Theme } from '@/common/types/api'
import { isApiError } from '@/common/api/errors'
import { PageHeader } from '@/common/components/PageHeader'
import { Button } from '@/common/components/ui/Button'
import { Card } from '@/common/components/ui/Card'
import { Input } from '@/common/components/ui/Input'
import { toast } from '@/common/components/ui/toastStore'
import { useTheme } from '@/common/theme/ThemeProvider'
import { authApi } from '@/features/auth/authApi'
import { useAuthStore } from '@/features/auth/authStore'
import { passwordSchema } from '@/features/auth/passwordRules'

const roleText: Record<Role, string[]> = {
  ANALYST: ['Ask questions and watch investigations', 'Upload documents and manage your own', 'View your own investigations, approvals and actions', 'You cannot decide approvals'],
  APPROVER: ['Read every investigation and document', 'Approve or reject high-impact actions (never your own requests)', 'You cannot start investigations or upload documents'],
  ADMIN: ['Everything an analyst and approver can see', 'Manage users, documents and the evaluation dashboard', 'You cannot approve actions from investigations you started'],
}
const pwSchema = z.object({ currentPassword: z.string().min(1, 'Enter your current password'), newPassword: passwordSchema, confirm: z.string() })
  .refine((v) => v.newPassword === v.confirm, { path: ['confirm'], message: 'Passwords do not match' })
type PwForm = z.infer<typeof pwSchema>

export function SettingsPage() {
  const { user, updateUser } = useAuthStore()
  const { theme, setTheme } = useTheme()
  const [name, setName] = useState(user?.displayName ?? '')
  const [savingName, setSavingName] = useState(false)
  const [nameError, setNameError] = useState<string | undefined>()
  const pw = useForm<PwForm>({ resolver: zodResolver(pwSchema), mode: 'onChange' })
  if (!user) return null

  const saveName = async () => {
    setSavingName(true); setNameError(undefined)
    try { updateUser(await authApi.updateProfile(name.trim())); toast.success('Profile saved') }
    catch (e) { setNameError(isApiError(e) ? (e.details?.displayName ?? e.display) : 'Could not save.') }
    finally { setSavingName(false) }
  }
  const changePw = pw.handleSubmit(async (v) => {
    try { await authApi.changePassword({ currentPassword: v.currentPassword, newPassword: v.newPassword }); toast.success('Password changed', 'Other sessions were signed out.'); pw.reset() }
    catch (e) {
      if (isApiError(e)) { Object.entries(e.details ?? {}).forEach(([k, m]) => k in v && pw.setError(k as keyof PwForm, { message: m })); toast.error('Password not changed', e.display) }
    }
  })
  const themes: { v: Theme; l: string }[] = [{ v: 'SYSTEM', l: 'Match my system' }, { v: 'LIGHT', l: 'Light' }, { v: 'DARK', l: 'Dark' }]

  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid max-w-3xl gap-6">
        <Card className="space-y-3"><h2 className="text-lg font-semibold">Profile</h2>
          <Input label="Display name" value={name} onChange={(e) => setName(e.target.value)} error={nameError} />
          <p className="text-sm text-muted">Signed in as {user.email}</p>
          <Button onClick={() => void saveName()} loading={savingName} disabled={!name.trim() || name.trim() === user.displayName}>Save profile</Button></Card>
        <Card><h2 className="mb-3 text-lg font-semibold">Change password</h2>
          <form onSubmit={(e) => void changePw(e)} className="space-y-3" noValidate>
            <Input label="Current password" type="password" autoComplete="current-password" error={pw.formState.errors.currentPassword?.message} {...pw.register('currentPassword')} />
            <Input label="New password" type="password" autoComplete="new-password" error={pw.formState.errors.newPassword?.message} {...pw.register('newPassword')} />
            <Input label="Confirm new password" type="password" autoComplete="new-password" error={pw.formState.errors.confirm?.message} {...pw.register('confirm')} />
            <Button type="submit" loading={pw.formState.isSubmitting} disabled={!pw.formState.isValid}>Change password</Button>
          </form></Card>
        <Card><fieldset><legend className="mb-3 text-lg font-semibold">Theme</legend>
          <div className="flex flex-wrap gap-4">{themes.map((t) => (
            <label key={t.v} className="flex items-center gap-2 text-sm"><input type="radio" name="theme" className="accent-[var(--accent)]" checked={theme === t.v} onChange={() => setTheme(t.v)} />{t.l}</label>))}</div></fieldset></Card>
        <Card><h2 className="mb-2 text-lg font-semibold">What your role can do</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">{roleText[user.role].map((t) => <li key={t}>{t}</li>)}</ul></Card>
        <Card><h2 className="mb-2 text-lg font-semibold">Privacy: what leaves your network</h2>
          <p className="text-sm">Questions and retrieved passages are sent to the language model provider to produce answers. When web search is on, only the text of each research step is sent to the search provider, with personal data such as emails and phone numbers removed first. Free-tier providers may keep or use requests, so use only synthetic or non-sensitive data. An organisation can run a local model to keep everything on its own servers.</p></Card>
        <Card><h2 className="mb-2 text-lg font-semibold">Keyboard shortcuts</h2>
          <p className="text-sm"><kbd className="rounded-sm border border-line-strong px-1">Ctrl</kbd> or <kbd className="rounded-sm border border-line-strong px-1">Cmd</kbd> + <kbd className="rounded-sm border border-line-strong px-1">K</kbd> opens the command palette. <kbd className="rounded-sm border border-line-strong px-1">Esc</kbd> closes any dialog.</p></Card>
      </div>
    </>
  )
}
