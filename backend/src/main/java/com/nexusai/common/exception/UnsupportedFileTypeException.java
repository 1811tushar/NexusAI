package com.nexusai.common.exception;

public class UnsupportedFileTypeException extends BusinessException {
    public UnsupportedFileTypeException(String message) { super(ErrorCode.UNSUPPORTED_FILE_TYPE, message); }
}
