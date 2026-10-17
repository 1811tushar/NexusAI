package com.nexusai.ai;

import java.util.List;

/** Contract section 6 InvestigateRequest. threadId is a UUID string; now is ISO-8601 UTC. */
public record AiInvestigateRequest(long investigationId, String threadId, long userId, String question, Options options, String now) {
    public record Options(boolean webSearch, List<Long> documentIds, boolean useMemory, int maxLoops) { }
}
