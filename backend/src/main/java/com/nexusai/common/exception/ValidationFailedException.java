package com.nexusai.common.exception;

import java.util.Map;

public class ValidationFailedException extends BusinessException {
    public ValidationFailedException(String message) { super(ErrorCode.VALIDATION_FAILED, message); }
    public ValidationFailedException(String message, Map<String, String> details) { super(ErrorCode.VALIDATION_FAILED, message, details); }
}
