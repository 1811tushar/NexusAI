import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { create } from 'zustand'
import { toast } from '@/common/components/ui/toastStore'
import { investigationApi } from './investigationApi'

const KEY = 'nx_watched_runs'
type Watched = Record<number, { question: string; notifiedApproval: boolean }>
const load = (): Watched => { try { return JSON.parse(sessionStorage.getItem(KEY) ?? '{}') as Watched } catch { return {} } }
const save = (w: Watched) => { try { sessionStorage.setItem(KEY, JSON.stringify(w)) } catch { /* storage unavailable */ } }

interface S { runs: Watched; watch: (id: number, question: string) => void; update: (id: number, patch: Partial<Watched[number]>) => void; drop: (id: number) => void }
export const useWatchStore = create<S>((set, get) => ({
  runs: load(),
  watch: (id, question) => { const runs = { ...get().runs, [id]: { question, notifiedApproval: false } }; save(runs); set({ runs }) },
  update: (id, patch) => { const cur = get().runs[id]; if (!cur) return; const runs = { ...get().runs, [id]: { ...cur, ...patch } }; save(runs); set({ runs }) },
  drop: (id) => { const { [id]: _gone, ...runs } = get().runs; save(runs); set({ runs }) },
}))
export const watchRun = (id: number, question: string) => useWatchStore.getState().watch(id, question)

/** Runs continue server-side when the user leaves the page; this announces completion with a toast (FE-IV-08). Mounted once in the shell. */
export function RunWatcher() {
  const runs = useWatchStore((s) => s.runs)
  const { pathname } = useLocation()
  const where = useRef(pathname); where.current = pathname
  const qc = useQueryClient()
  const ids = Object.keys(runs).join(',')

  useEffect(() => {
    if (!ids) return
    const tick = async () => {
      for (const id of ids.split(',').map(Number)) {
        try {
          const d = await investigationApi.get(id)
          const w = useWatchStore.getState().runs[id]
          const viewing = where.current === `/investigations/${id}`
          if (d.status === 'AWAITING_APPROVAL' && w && !w.notifiedApproval) {
            useWatchStore.getState().update(id, { notifiedApproval: true })
            if (!viewing) toast.info('Waiting for approval', d.question)
          }
          if (['COMPLETED', 'FAILED', 'CANCELLED', 'REFUSED'].includes(d.status)) {
            useWatchStore.getState().drop(id)
            void qc.invalidateQueries({ queryKey: ['investigation', id] }); void qc.invalidateQueries({ queryKey: ['investigations'] }); void qc.invalidateQueries({ queryKey: ['dashboard'] })
            if (!viewing) (d.status === 'COMPLETED' ? toast.success : toast.info)(`Investigation ${d.status.toLowerCase()}`, d.question)
          }
        } catch { useWatchStore.getState().drop(id) }
      }
    }
    const t = setInterval(() => void tick(), 5000)
    return () => clearInterval(t)
  }, [ids, qc])
  return null
}
