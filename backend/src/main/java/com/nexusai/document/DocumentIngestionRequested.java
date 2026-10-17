package com.nexusai.document;

/** Published inside the upload/reindex transaction; the listener starts ingestion only AFTER the commit. */
public record DocumentIngestionRequested(long documentId, String requestId) { }
