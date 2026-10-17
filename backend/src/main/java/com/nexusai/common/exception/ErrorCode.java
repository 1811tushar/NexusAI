package com.nexusai.common.exception;

/** Error catalogue from contract section 1. */
public enum ErrorCode {
    VALIDATION_FAILED(400), INVALID_CREDENTIALS(401), TOKEN_EXPIRED(401), UNAUTHENTICATED(401), FORBIDDEN(403),
    SELF_APPROVAL_NOT_ALLOWED(403), NOT_FOUND(404), DUPLICATE_RESOURCE(409), INVALID_STATE(409), FILE_TOO_LARGE(413),
    UNSUPPORTED_FILE_TYPE(415), QUOTA_EXCEEDED(422), INGESTION_FAILED(422), RATE_LIMITED(429),
    AI_SERVICE_UNAVAILABLE(503), LLM_RATE_LIMITED(503), INTERNAL_ERROR(500);

    private final int httpStatus;
    ErrorCode(int httpStatus) { this.httpStatus = httpStatus; }
    public int httpStatus() { return httpStatus; }
}
