import { create } from 'zustand'
import type { UserDTO } from '@/common/types/api'
import { refreshSession, setSessionLostHandler, tokenStore } from '@/common/api/httpClient'

interface AuthState {
  user: UserDTO | null
  restored: boolean
  setSession: (token: string, user: UserDTO) => void
  clear: () => void
  updateUser: (user: UserDTO) => void
  restore: () => Promise<void>
}
export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  restored: false,
  setSession: (token, user) => { tokenStore.set(token); set({ user, restored: true }) },
  clear: () => { tokenStore.set(null); set({ user: null, restored: true }) },
  updateUser: (user) => set({ user }),
  /** Silent restore from the httpOnly refresh cookie before protected routes render (FE-SH-04). */
  restore: async () => {
    if (get().restored) return
    const s = await refreshSession()
    if (s) set({ user: s.user, restored: true }); else set({ user: null, restored: true })
  },
}))
setSessionLostHandler(() => useAuthStore.getState().clear())
