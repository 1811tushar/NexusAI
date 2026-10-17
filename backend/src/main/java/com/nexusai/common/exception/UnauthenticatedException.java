package com.nexusai.common.exception;

public class UnauthenticatedException extends BusinessException {
    public UnauthenticatedException(String message) { super(ErrorCode.UNAUTHENTICATED, message); }
}
