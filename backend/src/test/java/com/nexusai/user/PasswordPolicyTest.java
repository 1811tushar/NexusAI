package com.nexusai.user;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.nexusai.common.exception.ValidationFailedException;
import org.junit.jupiter.api.Test;

class PasswordPolicyTest {
    @Test void acceptsLetterAndDigitAtTenChars() { assertThatCode(() -> PasswordPolicy.validate("abcdefgh12")).doesNotThrowAnyException(); }
    @Test void rejectsShort() { assertThatThrownBy(() -> PasswordPolicy.validate("abc12345")).isInstanceOf(ValidationFailedException.class); }
    @Test void rejectsNoDigit() { assertThatThrownBy(() -> PasswordPolicy.validate("abcdefghijkl")).isInstanceOf(ValidationFailedException.class); }
    @Test void rejectsNoLetter() { assertThatThrownBy(() -> PasswordPolicy.validate("1234567890123")).isInstanceOf(ValidationFailedException.class); }
    @Test void rejectsOverBcryptLimit() { assertThatThrownBy(() -> PasswordPolicy.validate("a1".repeat(40))).isInstanceOf(ValidationFailedException.class); }
    @Test void rejectsNull() { assertThatThrownBy(() -> PasswordPolicy.validate(null)).isInstanceOf(ValidationFailedException.class); }
}
