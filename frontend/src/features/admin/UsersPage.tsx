import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { UserPlus } from 'lucide-react'
import { http } from '@/common/api/httpClient'
import { isApiError } from '@/common/api/errors'
import type { PagedResponse, Role, UserDTO } from '@/common/types/api'
import { PageHeader } from '@/common/components/PageHeader'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { Avatar } from '@/common/components/ui/Avatar'
import { Button } from '@/common/components/ui/Button'
import { Dialog, DialogContent } from '@/common/components/ui/Dialog'
import { Input } from '@/common/components/ui/Input'
import { Select } from '@/common/components/ui/Select'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Switch } from '@/common/components/ui/Switch'
import { Table, TBody, TD, TH, THead, TR } from '@/common/components/ui/Table'
import { toast } from '@/common/components/ui/toastStore'
import { useDebounce } from '@/common/hooks/useDebounce'
import { formatDate } from '@/common/utils/format'
import { useAuthStore } from '@/features/auth/authStore'
import { passwordSchema } from '@/features/auth/passwordRules'

const roles: { value: Role; label: string }[] = [{ value: 'ANALYST', label: 'Analyst' }, { value: 'APPROVER', label: 'Approver' }, { value: 'ADMIN', label: 'Admin' }]
const adminApi = {
  list: (q: string, role: string, page: number) => http.get<PagedResponse<UserDTO>>('/admin/users', { q, role, page, size: 20 }),
  create: (b: { email: string; displayName: string; role: Role; temporaryPassword: string }) => http.post<UserDTO>('/admin/users', b),
  patch: (id: number, b: { role?: Role; enabled?: boolean }) => http.patch<UserDTO>(`/admin/users/${id}`, b),
}
const schema = z.object({ displayName: z.string().trim().min(1, 'Enter a name'), email: z.string().email('Enter a valid email address'), role: z.enum(['ANALYST', 'APPROVER', 'ADMIN']), temporaryPassword: passwordSchema })
type Form = z.infer<typeof schema>

function CreateUserDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (o: boolean) => void; onCreated: () => void }) {
  const { register, handleSubmit, setError, reset, formState: { errors, isValid, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema), mode: 'onChange', defaultValues: { role: 'ANALYST' } })
  const submit = handleSubmit(async (v) => {
    try { await adminApi.create(v); toast.success('User created', `${v.email} can sign in with the temporary password.`); reset(); onCreated(); onOpenChange(false) }
    catch (e) { if (isApiError(e)) { Object.entries(e.details ?? {}).forEach(([k, m]) => k in v && setError(k as keyof Form, { message: m })); toast.error('User not created', e.display) } }
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Create a user" description="They should change the temporary password after first sign-in.">
        <form onSubmit={(e) => void submit(e)} className="space-y-3" noValidate>
          <Input label="Name" error={errors.displayName?.message} {...register('displayName')} />
          <Input label="Email" type="email" error={errors.email?.message} {...register('email')} />
          <Select label="Role" options={roles} {...register('role')} className="w-full" />
          <Input label="Temporary password" type="password" autoComplete="new-password" error={errors.temporaryPassword?.message} {...register('temporaryPassword')} />
          <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" loading={isSubmitting} disabled={!isValid}>Create user</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function UsersPage() {
  const me = useAuthStore((s) => s.user)
  const qc = useQueryClient()
  const [q, setQ] = useState(''); const [role, setRole] = useState(''); const [page, setPage] = useState(0); const [creating, setCreating] = useState(false)
  const dq = useDebounce(q.trim(), 300)
  const list = useQuery({ queryKey: ['admin-users', dq, role, page], queryFn: () => adminApi.list(dq, role, page), placeholderData: keepPreviousData })
  // Server guard messages (last admin, self-protection) are shown verbatim.
  const patch = useMutation({
    mutationFn: (v: { id: number; body: { role?: Role; enabled?: boolean } }) => adminApi.patch(v.id, v.body),
    onSuccess: () => toast.success('User updated'),
    onError: (e) => toast.error('Change not applied', isApiError(e) ? e.display : undefined),
    onSettled: () => void qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
  return (
    <>
      <PageHeader title="Users" description="Create accounts and control who can do what." actions={<Button onClick={() => setCreating(true)}><UserPlus className="h-4 w-4" aria-hidden />Create user</Button>} />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1"><Input label="Search users" value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }} placeholder="Name or email" /></div>
        <Select label="Role filter" value={role} onChange={(e) => { setRole(e.target.value); setPage(0) }} options={[{ value: '', label: 'All roles' }, ...roles]} />
      </div>
      {list.isPending ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>
        : list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} />
        : list.data.items.length === 0 ? <EmptyState title="No users match" hint="Clear the search or the role filter." />
        : (
          <>
            <Table aria-label="Users">
              <THead><TR><TH>User</TH><TH>Role</TH><TH>Active</TH><TH>Created</TH></TR></THead>
              <TBody>{list.data.items.map((u) => (
                <TR key={u.id}>
                  <TD><div className="flex items-center gap-3"><Avatar name={u.displayName} /><div><p className="font-medium">{u.displayName}{u.id === me?.id && <span className="text-muted"> (you)</span>}</p><p className="text-xs text-muted">{u.email}</p></div></div></TD>
                  <TD><Select label={`Role for ${u.displayName}`} hideLabel value={u.role} options={roles} onChange={(e) => patch.mutate({ id: u.id, body: { role: e.target.value as Role } })} /></TD>
                  <TD><Switch label={`${u.displayName} is active`} checked={u.enabled} onCheckedChange={(enabled) => patch.mutate({ id: u.id, body: { enabled } })} /></TD>
                  <TD className="whitespace-nowrap">{formatDate(u.createdAt)}</TD>
                </TR>))}</TBody>
            </Table>
            <div className="mt-3 flex items-center justify-between text-sm"><span className="text-muted">Page {list.data.page + 1} of {list.data.totalPages}</span>
              <div className="flex gap-2"><Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                <Button variant="secondary" size="sm" disabled={page + 1 >= list.data.totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button></div></div>
          </>
        )}
      <CreateUserDialog open={creating} onOpenChange={setCreating} onCreated={() => void qc.invalidateQueries({ queryKey: ['admin-users'] })} />
    </>
  )
}
