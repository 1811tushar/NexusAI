package com.nexusai.common.exception;

public class QuotaExceededException extends BusinessException {
    public QuotaExceededException(String message) { super(ErrorCode.QUOTA_EXCEEDED, message); }
}
