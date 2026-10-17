import { http } from '@/common/api/httpClient'
import type { EvalRunDTO, EvalRunDetailDTO } from './types'
export const evalApi = { runs: () => http.get<EvalRunDTO[]>('/eval/runs'), run: (id: number) => http.get<EvalRunDetailDTO>(`/eval/runs/${id}`) }
