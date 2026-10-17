package com.nexusai.common.exception;

public class AiServiceUnavailableException extends BusinessException {
    public AiServiceUnavailableException(String message) { super(ErrorCode.AI_SERVICE_UNAVAILABLE, message); }
    public AiServiceUnavailableException(String message, Throwable cause) { super(ErrorCode.AI_SERVICE_UNAVAILABLE, message, null, cause); }
}
