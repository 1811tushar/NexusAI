package com.nexusai.audit;

/** Audit action names (BE-PL-09). Backend B may add its own constants here. */
public final class AuditAction {
    public static final String LOGIN_SUCCESS = "LOGIN_SUCCESS";
    public static final String LOGIN_FAILURE = "LOGIN_FAILURE";
    public static final String LOGIN_BLOCKED = "LOGIN_BLOCKED";
    public static final String REFRESH_REUSE = "REFRESH_REUSE_DETECTED";
    public static final String REGISTER = "REGISTER";
    public static final String PASSWORD_CHANGE = "PASSWORD_CHANGE";
    public static final String ROLE_CHANGE = "ROLE_CHANGE";
    public static final String USER_CREATE = "USER_CREATE";
    public static final String USER_ENABLE = "USER_ENABLE";
    public static final String USER_DISABLE = "USER_DISABLE";
    public static final String DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD";
    public static final String DOCUMENT_DELETE = "DOCUMENT_DELETE";
    public static final String APPROVAL_DECISION = "APPROVAL_DECISION";
    private AuditAction() { }
}
