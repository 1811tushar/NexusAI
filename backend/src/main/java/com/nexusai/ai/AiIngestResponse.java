package com.nexusai.ai;

import java.util.List;

public record AiIngestResponse(long documentId, Integer pageCount, int chunkCount, List<String> warnings) { }
