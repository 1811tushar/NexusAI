import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/common/components/ui/Button'
import { Input } from '@/common/components/ui/Input'
import { isApiError } from '@/common/api/errors'
import { authApi } from './authApi'
import { useAuthStore } from './authStore'
import { passwordSchema } from './passwordRules'

const schema = z.object({ displayName: z.string().trim().min(1, 'Enter your name').max(80), email: z.string().email('Enter a valid email address'), password: passwordSchema })
type Form = z.infer<typeof schema>

export function RegisterPage() {
  const nav = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const [closed, setClosed] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const { register, handleSubmit, setError, formState: { errors, isValid, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema), mode: 'onChange' })

  const onSubmit = async (v: Form) => {
    setFormError(null)
    try { const r = await authApi.register(v); setSession(r.accessToken, r.user); nav('/', { replace: true }) }
    catch (e) {
      if (!isApiError(e)) return setFormError('Could not create the account. Try again.')
      // Registration is controlled server-side (REGISTRATION_OPEN); a refusal means self-sign-up is off.
      if (e.status === 403 || e.status === 404) return setClosed(true)
      Object.entries(e.details ?? {}).forEach(([k, m]) => k in v && setError(k as keyof Form, { message: m }))
      setFormError(e.display)
    }
  }
  return (
    <main className="mx-auto mt-20 w-full max-w-sm px-4">
      <h1 className="text-2xl font-semibold">Create your account</h1>
      {closed ? (
        <div role="alert" className="mt-6 rounded-md border border-line bg-surface p-4">
          <p className="font-medium">Self sign-up is turned off</p>
          <p className="mt-1 text-sm text-muted">Ask an administrator to create an account for you, then sign in.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
          <Input label="Name" autoComplete="name" error={errors.displayName?.message} {...register('displayName')} />
          <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
          <Input label="Password" type="password" autoComplete="new-password" error={errors.password?.message} {...register('password')} />
          {formError && <p role="alert" className="text-sm text-danger">{formError}</p>}
          <Button type="submit" className="w-full" loading={isSubmitting} disabled={!isValid}>Create account</Button>
        </form>
      )}
      <p className="mt-4 text-sm text-muted">Already have an account? <Link className="text-accent underline" to="/login">Sign in</Link></p>
    </main>
  )
}
