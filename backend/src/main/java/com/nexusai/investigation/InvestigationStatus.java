package com.nexusai.investigation;

public enum InvestigationStatus {
    RUNNING, AWAITING_APPROVAL, COMPLETED, FAILED, CANCELLED,
    /** Blocked by the input guardrail (contract v2.1): terminal, nothing was executed. */
    REFUSED;

    public boolean isTerminal() { return this == COMPLETED || this == FAILED || this == CANCELLED || this == REFUSED; }
}
