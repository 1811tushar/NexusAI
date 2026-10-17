from app.core.pii import contains_pii, luhn_valid, redact, redact_text, verhoeff_valid


def _aadhaar(first11: str) -> str:
    return next(first11 + str(d) for d in range(10) if verhoeff_valid(first11 + str(d)))


def test_email_phone_card_ssn_pan_redacted():
    r = redact("Mail jane.doe@example.com, call +91 98765 43210, card 4111 1111 1111 1111, SSN 123-45-6789, PAN ABCDE1234F")
    assert r.counts == {"EMAIL": 1, "PHONE": 1, "CARD": 1, "SSN": 1, "PAN": 1}
    for raw in ("jane.doe", "98765", "4111", "123-45-6789", "ABCDE1234F"):
        assert raw not in r.text


def test_card_requires_valid_luhn():
    assert luhn_valid("4111111111111111") and not luhn_valid("4111111111111112")
    assert not contains_pii("order ref 4111 1111 1111 1112")


def test_aadhaar_uses_verhoeff():
    good = _aadhaar("23456789012")
    assert "[REDACTED_AADHAAR]" in redact_text(f"id {good[:4]} {good[4:8]} {good[8:]}")
    bad = good[:-1] + str((int(good[-1]) + 1) % 10)
    assert not contains_pii(f"id {bad}")


def test_business_numbers_and_dates_survive():
    text = "Q2 revenue 4821930.55 vs 1,250,000 units on 2026-06-30 and 30/06/2026; margin 12.5%; sku 20250630"
    assert redact_text(text) == text


def test_counts_never_contain_values_and_idempotent():
    r = redact("bob@corp.io")
    assert "bob" not in r.to_guardrail_detail() and r.to_guardrail_detail() == "Redacted 1 EMAIL"
    assert redact_text(r.text) == r.text
