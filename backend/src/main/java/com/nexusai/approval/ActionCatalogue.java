package com.nexusai.approval;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.user.Role;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Component;

/**
 * Contract section 8: the only actions that exist. Risk is looked up here, never taken from the event. Params are re-validated
 * (Python already did) because Spring is the only place where actions "happen". Unknown extra fields are ignored; missing,
 * mistyped or out-of-range fields are errors.
 */
@Component
public class ActionCatalogue {
    public Optional<ActionType> parse(String raw) {
        if (raw == null) return Optional.empty();
        try {
            return Optional.of(ActionType.valueOf(raw.trim()));
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    public Risk riskOf(ActionType t) { return t.risk(); }

    /** @return validation errors; empty list = valid. */
    public List<String> validate(ActionType type, JsonNode p) {
        List<String> errors = new ArrayList<>();
        if (p == null || !p.isObject()) return List.of("params must be an object");
        switch (type) {
            case FLAG_FOR_REVIEW -> { text(p, "subject", 200, errors); text(p, "reason", 2000, errors); }
            case SAVE_INSIGHT -> { text(p, "title", 200, errors); text(p, "text", 4000, errors); }
            case CREATE_FOLLOWUP_TASK -> {
                text(p, "title", 200, errors);
                String role = text(p, "ownerRole", 20, errors);
                if (role != null) {
                    try { Role.valueOf(role); } catch (IllegalArgumentException e) { errors.add("ownerRole must be ADMIN, ANALYST or APPROVER"); }
                }
                integer(p, "dueInDays", 0, 365, errors);
            }
            case ADJUST_PRICE -> {
                integer(p, "productId", 1, Long.MAX_VALUE, errors);
                JsonNode c = p.get("changePct");
                if (c == null || !c.isNumber()) errors.add("changePct must be a number");
                else if (Math.abs(c.asDouble()) > 30.0) errors.add("|changePct| must be <= 30");
                else if (c.asDouble() == 0.0) errors.add("changePct must not be 0");
            }
            case PAUSE_CAMPAIGN -> {
                integer(p, "regionId", 1, Long.MAX_VALUE, errors);
                text(p, "channel", 30, errors);
                integer(p, "weeks", 1, 52, errors);
            }
            case REALLOCATE_BUDGET -> {
                Long from = integer(p, "fromRegionId", 1, Long.MAX_VALUE, errors);
                Long to = integer(p, "toRegionId", 1, Long.MAX_VALUE, errors);
                if (from != null && from.equals(to)) errors.add("fromRegionId and toRegionId must differ");
                JsonNode a = p.get("amount");
                if (a == null || !a.isNumber() || a.asDouble() <= 0) errors.add("amount must be a positive number");
            }
        }
        return errors;
    }

    private static String text(JsonNode p, String field, int max, List<String> errors) {
        JsonNode n = p.get(field);
        if (n == null || !n.isTextual() || n.asText().isBlank()) { errors.add(field + " must be a non-empty string"); return null; }
        if (n.asText().length() > max) { errors.add(field + " is longer than " + max + " characters"); return null; }
        return n.asText();
    }

    private static Long integer(JsonNode p, String field, long min, long max, List<String> errors) {
        JsonNode n = p.get(field);
        if (n == null || !n.isIntegralNumber()) { errors.add(field + " must be an integer"); return null; }
        long v = n.asLong();
        if (v < min || v > max) { errors.add(field + " is out of range"); return null; }
        return v;
    }
}
