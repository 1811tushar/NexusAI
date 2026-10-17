import { create } from 'zustand'
/** Set by httpClient on network failure / success; read by the backend-unreachable banner (FE-SH-06). */
export const useNetworkStatus = create<{ unreachable: boolean; setUnreachable: (v: boolean) => void }>((set) => ({
  unreachable: false, setUnreachable: (unreachable) => set({ unreachable }),
}))
