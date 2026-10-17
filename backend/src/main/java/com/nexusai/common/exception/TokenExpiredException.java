package com.nexusai.common.exception;

public class TokenExpiredException extends BusinessException {
    public TokenExpiredException(String message) { super(ErrorCode.TOKEN_EXPIRED, message); }
}
