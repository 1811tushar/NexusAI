package com.nexusai.ai;

import java.util.List;

/** Contract section 6 ResumeRequest. decidedBy is a display name only; Python never receives role data. */
public record AiResumeRequest(long investigationId, List<Decision> decisions) {
    public record Decision(String actionKey, long approvalId, String decision, String decidedBy, String comment) { }
}
