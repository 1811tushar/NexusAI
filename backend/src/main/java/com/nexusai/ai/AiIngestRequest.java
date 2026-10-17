package com.nexusai.ai;

import com.nexusai.document.SourceType;

/** Contract section 6 IngestRequest (sent as the multipart "meta" part). */
public record AiIngestRequest(long documentId, long uploadedByUserId, SourceType sourceType, String title, String filename) { }
