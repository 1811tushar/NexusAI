package com.nexusai.common.exception;

public class IngestionFailedException extends BusinessException {
    public IngestionFailedException(String message) { super(ErrorCode.INGESTION_FAILED, message); }
}
