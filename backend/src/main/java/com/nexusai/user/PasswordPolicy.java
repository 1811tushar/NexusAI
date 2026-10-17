package com.nexusai.user;

import com.nexusai.common.exception.ValidationFailedException;
import java.nio.charset.StandardCharsets;
import java.util.Map;

/** Contract 4.1: >= 10 chars with a letter and a digit. Upper bound = BCrypt's 72-byte input limit. */
public final class PasswordPolicy {
    public static final int MIN_LENGTH = 10;
    public static final int MAX_BYTES = 72;
    private PasswordPolicy() { }

    public static void validate(String password) { validate(password, "password"); }

    public static void validate(String password, String field) {
        String problem = null;
        if (password == null || password.length() < MIN_LENGTH) problem = "must be at least " + MIN_LENGTH + " characters";
        else if (password.getBytes(StandardCharsets.UTF_8).length > MAX_BYTES) problem = "must be at most " + MAX_BYTES + " bytes";
        else if (password.chars().noneMatch(Character::isLetter)) problem = "must contain a letter";
        else if (password.chars().noneMatch(Character::isDigit)) problem = "must contain a digit";
        if (problem != null) throw new ValidationFailedException("Password does not meet the policy", Map.of(field, problem));
    }
}
