// Mirrors API contract v2.1. Change the contract first, then this file.
export interface ApiError { code: ErrorCode; message: string; details?: Record<string, string>; requestId?: string }
export interface ApiResponse<T> { success: boolean; data: T | null; error: ApiError | null }
export interface PagedResponse<T> { items: T[]; page: number; size: number; totalItems: number; totalPages: number }

export type ErrorCode =
  | 'VALIDATION_FAILED' | 'INVALID_CREDENTIALS' | 'TOKEN_EXPIRED' | 'UNAUTHENTICATED' | 'FORBIDDEN'
  | 'SELF_APPROVAL_NOT_ALLOWED' | 'NOT_FOUND' | 'DUPLICATE_RESOURCE' | 'INVALID_STATE' | 'FILE_TOO_LARGE'
  | 'UNSUPPORTED_FILE_TYPE' | 'QUOTA_EXCEEDED' | 'INGESTION_FAILED' | 'RATE_LIMITED'
  | 'AI_SERVICE_UNAVAILABLE' | 'LLM_RATE_LIMITED' | 'INTERNAL_ERROR' | 'NETWORK_ERROR'

export type Role = 'ADMIN' | 'ANALYST' | 'APPROVER'
export type SourceType = 'PDF' | 'DOCX' | 'TXT' | 'MD'
export type DocumentStatus = 'UPLOADED' | 'INGESTING' | 'READY' | 'FAILED' | 'DELETING'
export type InvestigationStatus = 'RUNNING' | 'AWAITING_APPROVAL' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'REFUSED'
export type ClaimStatus = 'VERIFIED' | 'UNSUPPORTED' | 'CONTRADICTED'
export type EvidenceKind = 'DOCUMENT' | 'SQL' | 'STATS' | 'WEB' | 'MEMORY'
export type Risk = 'LOW' | 'HIGH'
export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED'
export type ActionType =
  | 'FLAG_FOR_REVIEW' | 'CREATE_FOLLOWUP_TASK' | 'SAVE_INSIGHT' | 'ADJUST_PRICE' | 'PAUSE_CAMPAIGN' | 'REALLOCATE_BUDGET'
export type ActionStatus = 'EXECUTED' | 'REJECTED' | 'EXPIRED' | 'FAILED'
export type AgentName = 'SUPERVISOR' | 'PLANNER' | 'RESEARCHER' | 'DATA_ANALYST' | 'ANALYST' | 'VERIFIER' | 'REPORTER'
export type Theme = 'SYSTEM' | 'LIGHT' | 'DARK'
export type GuardrailStage = 'INPUT' | 'TOOL' | 'OUTPUT'
export type GuardrailAction = 'BLOCKED' | 'REDACTED' | 'FLAGGED'
export type GuardrailCategory = 'PROMPT_INJECTION' | 'OFF_TOPIC' | 'UNSAFE_REQUEST' | 'PII' | 'INVALID_CITATION' | 'INVALID_OUTPUT'

export interface UserDTO { id: number; email: string; displayName: string; role: Role; enabled: boolean; createdAt: string }
export interface RegisterRequest { email: string; password: string; displayName: string }
export interface LoginRequest { email: string; password: string }
export interface AuthResponse { accessToken: string; expiresInSeconds: number; user: UserDTO }

export interface DocumentDTO {
  id: number; title: string; originalFilename: string; sourceType: SourceType; mimeType: string; sizeBytes: number
  status: DocumentStatus; errorMessage: string | null; pageCount: number | null; chunkCount: number | null
  uploadedBy: { id: number; displayName: string }; createdAt: string; ingestedAt: string | null
}
export interface ChunkDTO { id: number; chunkIndex: number; page: number | null; section: string | null; content: string }
export type SearchMode = 'HYBRID' | 'VECTOR' | 'KEYWORD'
export interface SearchResultDTO { chunkId: number; documentId: number; documentTitle: string; page: number | null; section: string | null; snippet: string; score: number }
export interface MemoryDTO { id: number; summary: string; sourceInvestigationId: number | null; importance: number; createdAt: string; lastAccessedAt: string | null }
export interface InvestigationDTO {
  id: number; question: string; status: InvestigationStatus; confidence: number | null; loopsUsed: number; summary: string | null
  owner: { id: number; displayName: string }; pendingApprovals: number; createdAt: string; completedAt: string | null
}
export interface DashboardSummaryDTO {
  investigationsByStatus: Record<InvestigationStatus, number>; pendingApprovals: number; documentsReady: number
  avgConfidence30d: number | null; recent: InvestigationDTO[]
}
