package com.nexusai.common.exception;

import java.util.Map;

/** Base class of every expected, client-visible failure. Mapped to the ApiResponse envelope by GlobalExceptionHandler. */
public class BusinessException extends RuntimeException {
    private final transient ErrorCode code;
    private final transient Map<String, String> details;

    public BusinessException(ErrorCode code, String message) { this(code, message, null, null); }
    public BusinessException(ErrorCode code, String message, Map<String, String> details) { this(code, message, details, null); }
    public BusinessException(ErrorCode code, String message, Map<String, String> details, Throwable cause) {
        super(message, cause);
        this.code = code;
        this.details = details;
    }
    public ErrorCode getCode() { return code; }
    public Map<String, String> getDetails() { return details; }
}
