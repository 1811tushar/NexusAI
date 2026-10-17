package com.nexusai.approval;

/** Contract section 8. Risk is FIXED here and never taken from the LLM. */
public enum ActionType {
    FLAG_FOR_REVIEW(Risk.LOW), CREATE_FOLLOWUP_TASK(Risk.LOW), SAVE_INSIGHT(Risk.LOW),
    ADJUST_PRICE(Risk.HIGH), PAUSE_CAMPAIGN(Risk.HIGH), REALLOCATE_BUDGET(Risk.HIGH);

    private final Risk risk;
    ActionType(Risk risk) { this.risk = risk; }
    public Risk risk() { return risk; }
}
