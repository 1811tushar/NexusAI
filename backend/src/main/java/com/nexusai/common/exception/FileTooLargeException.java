package com.nexusai.common.exception;

public class FileTooLargeException extends BusinessException {
    public FileTooLargeException(String message) { super(ErrorCode.FILE_TOO_LARGE, message); }
}
