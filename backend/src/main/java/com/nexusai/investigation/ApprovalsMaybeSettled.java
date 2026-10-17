package com.nexusai.investigation;

/** Published by the relay when a stream ended after approval_required: ApprovalFlowService resumes the run if nothing is pending. */
public record ApprovalsMaybeSettled(long investigationId) { }
