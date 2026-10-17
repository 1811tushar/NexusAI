package com.nexusai.common.exception;

public class InvalidCredentialsException extends BusinessException {
    public InvalidCredentialsException() { super(ErrorCode.INVALID_CREDENTIALS, "Invalid credentials, or the account is temporarily locked."); }
}
