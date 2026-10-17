import type { ApiError as ApiErrorShape, ErrorCode } from '@/common/types/api'

export class ApiError extends Error implements ApiErrorShape {
  constructor(
    public code: ErrorCode,
    message: string,
    public status: number,
    public details?: Record<string, string>,
    public requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
  /** Message safe to show: unknown errors expose the request id for support. */
  get display(): string {
    return this.code === 'INTERNAL_ERROR' && this.requestId ? `${this.message} (request ${this.requestId})` : this.message
  }
}
export const isApiError = (e: unknown): e is ApiError => e instanceof ApiError
