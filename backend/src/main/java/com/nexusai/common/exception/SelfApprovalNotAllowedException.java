package com.nexusai.common.exception;

public class SelfApprovalNotAllowedException extends BusinessException {
    public SelfApprovalNotAllowedException() { super(ErrorCode.SELF_APPROVAL_NOT_ALLOWED, "You cannot decide an approval for an investigation you started."); }
}
