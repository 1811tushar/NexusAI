import { http } from 'msw'
import { buildEval } from '../fixtures'
import { fail, ok } from '../util'
import { currentUser } from './auth'

let cache: ReturnType<typeof buildEval> | null = null
const data = () => (cache ??= buildEval())
export const evalHandlers = [
  http.get('/api/eval/runs', () => (currentUser()?.role === 'ADMIN' ? ok(data().runs) : fail('FORBIDDEN', 'Administrators only.'))),
  http.get('/api/eval/runs/:id', ({ params }) => {
    if (currentUser()?.role !== 'ADMIN') return fail('FORBIDDEN', 'Administrators only.')
    const d = data().details.get(Number(params.id)); return d ? ok(d) : fail('NOT_FOUND', 'Run not found.')
  }),
]
