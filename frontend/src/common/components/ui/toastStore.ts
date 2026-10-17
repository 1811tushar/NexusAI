import { create } from 'zustand'

export type ToastTone = 'success' | 'error' | 'info'
export interface ToastItem { id: number; tone: ToastTone; title: string; description?: string }
interface State {
  toasts: ToastItem[]
  announcement: string
  push: (t: Omit<ToastItem, 'id'>) => void
  dismiss: (id: number) => void
  announce: (msg: string) => void
}
let seq = 0
export const useToastStore = create<State>((set, get) => ({
  toasts: [], announcement: '',
  push: (t) => {
    const id = ++seq
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }))
    setTimeout(() => get().dismiss(id), t.tone === 'error' ? 8000 : 5000)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
  announce: (msg) => { set({ announcement: '' }); setTimeout(() => set({ announcement: msg }), 50) },
}))
const push = (tone: ToastTone) => (title: string, description?: string) => useToastStore.getState().push({ tone, title, description })
export const toast = { success: push('success'), error: push('error'), info: push('info') }
/** Polite live-region message for key milestones only (FE-A11-03). Frontend B uses this for plan ready / approval needed / completed. */
export const announce = (msg: string) => useToastStore.getState().announce(msg)
