import { http, tokenStore } from '@/common/api/httpClient'
import type { AuthResponse, LoginRequest, RegisterRequest, UserDTO } from '@/common/types/api'

export const authApi = {
  login: (b: LoginRequest) => http.post<AuthResponse>('/auth/login', b, { skipAuth: true }),
  register: (b: RegisterRequest) => http.post<AuthResponse>('/auth/register', b, { skipAuth: true }),
  logout: async () => { try { await http.post<null>('/auth/logout') } finally { tokenStore.set(null) } },
  me: () => http.get<UserDTO>('/auth/me'),
  updateProfile: (displayName: string) => http.patch<UserDTO>('/users/me', { displayName }),
  changePassword: (b: { currentPassword: string; newPassword: string }) => http.post<null>('/users/me/password', b),
}
