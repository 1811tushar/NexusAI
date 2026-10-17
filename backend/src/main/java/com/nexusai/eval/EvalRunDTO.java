package com.nexusai.eval;

import java.time.Instant;

/** Contract 4.5 (v2.1): four systems, optional variant, extra metrics. Unknown fields from Python are ignored. */
public record EvalRunDTO(Long id, Instant createdAt, String variant, String system, int questionCount, Metrics metrics) {
    public record Metrics(double answerCorrectness, double groundedClaimsShare, double hallucinationRate, double avgLatencyMs, double avgTokens,
                          Double approvalGateCompliance, Double retrievalHitRate, Double citationValidity, Double guardrailBlockRate,
                          Double failureRecoveryRate) { }
}
