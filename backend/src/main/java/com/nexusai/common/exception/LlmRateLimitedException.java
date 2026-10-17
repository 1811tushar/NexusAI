package com.nexusai.common.exception;

public class LlmRateLimitedException extends BusinessException {
    public LlmRateLimitedException(String message) { super(ErrorCode.LLM_RATE_LIMITED, message); }
}
