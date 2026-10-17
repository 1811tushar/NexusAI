package com.nexusai.common.exception;

public class ResourceNotFoundException extends BusinessException {
    public ResourceNotFoundException(String message) { super(ErrorCode.NOT_FOUND, message); }
}
