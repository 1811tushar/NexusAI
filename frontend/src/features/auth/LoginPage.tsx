import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/common/components/ui/Button'
import { Input } from '@/common/components/ui/Input'
import { isApiError } from '@/common/api/errors'
import { authApi } from './authApi'
import { useAuthStore } from './authStore'

const schema = z.object({ email: z.string().email('Enter a valid email address'), password: z.string().min(1, 'Enter your password') })
type Form = z.infer<typeof schema>

export function LoginPage() {
  const nav = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/'
  const setSession = useAuthStore((s) => s.setSession)
  const [formError, setFormError] = useState<string | null>(null)
  const { register, handleSubmit, setError, formState: { errors, isValid, isSubmitting } } =
    useForm<Form>({ resolver: zodResolver(schema), mode: 'onChange' })

  const onSubmit = async (v: Form) => {
    setFormError(null)
    try {
      const r = await authApi.login(v)
      setSession(r.accessToken, r.user)
      nav(from, { replace: true })
    } catch (e) {
      if (isApiError(e)) {
        Object.entries(e.details ?? {}).forEach(([k, m]) => k in v && setError(k as keyof Form, { message: m }))
        setFormError(e.display)
      } else setFormError('Could not sign in. Try again.')
    }
  }
  return (
    <main className="mx-auto mt-20 w-full max-w-sm px-4">
      <h1 className="text-2xl font-semibold">Sign in to NexusAI</h1>
      <p className="mt-1 text-muted">Ask business questions and review what the agents found.</p>
      <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
        <Input label="Email" type="email" autoComplete="username" error={errors.email?.message} {...register('email')} />
        <Input label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
        {formError && <p role="alert" className="text-sm text-danger">{formError}</p>}
        <Button type="submit" className="w-full" loading={isSubmitting} disabled={!isValid}>Sign in</Button>
      </form>
      <p className="mt-4 text-sm text-muted">New here? <Link className="text-accent underline" to="/register">Create an account</Link></p>
    </main>
  )
}
