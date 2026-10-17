import type { DocumentDTO, Role, UserDTO } from '@/common/types/api'
/** UI hints only; the server is the authority (contract section 2). */
export const canUpload = (role?: Role) => role === 'ADMIN' || role === 'ANALYST'
export const canManageDoc = (user: UserDTO | null, d: DocumentDTO) =>
  !!user && (user.role === 'ADMIN' || (user.role === 'ANALYST' && d.uploadedBy.id === user.id))
