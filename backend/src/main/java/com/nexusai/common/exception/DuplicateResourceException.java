package com.nexusai.common.exception;

import java.util.Map;

public class DuplicateResourceException extends BusinessException {
    public DuplicateResourceException(String message) { super(ErrorCode.DUPLICATE_RESOURCE, message); }
    public DuplicateResourceException(String message, Map<String, String> details) { super(ErrorCode.DUPLICATE_RESOURCE, message, details); }
}
