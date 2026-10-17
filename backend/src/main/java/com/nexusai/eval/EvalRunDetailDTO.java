package com.nexusai.eval;

import java.time.Instant;
import java.util.List;

public record EvalRunDetailDTO(Long id, Instant createdAt, String variant, String system, int questionCount, EvalRunDTO.Metrics metrics,
                               List<Result> results) {
    /** category: NORMAL | EDGE | ADVERSARIAL | MISSING_DATA | TOOL_FAILURE */
    public record Result(String questionId, String category, String question, List<String> expectedFacts, String answer, boolean correct,
                         double groundedShare, boolean hallucinated, long latencyMs) { }
}
