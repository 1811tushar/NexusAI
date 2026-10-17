package com.nexusai.investigation;

import java.util.List;

/** question 10..2000 chars is validated in InvestigationService so the error carries field details and trimmed length. */
public record StartInvestigationRequestDTO(String question, Options options) {
    public record Options(Boolean webSearch, List<Long> documentIds, Boolean useMemory, Integer maxLoops) { }
}
