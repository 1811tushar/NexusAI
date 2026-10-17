package com.nexusai.common.util;

import com.nexusai.common.exception.ValidationFailedException;
import java.util.Map;
import java.util.Set;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;

public final class PageUtil {
    public static final int MAX_SIZE = 100;
    private PageUtil() { }

    /** page is 0-based, size is clamped to 1..100, sort is "field,asc|desc" restricted to an allow-list. */
    public static Pageable of(int page, int size, String sort, Set<String> allowedFields, String defaultField, Sort.Direction defaultDir) {
        String field = defaultField;
        Sort.Direction dir = defaultDir;
        if (sort != null && !sort.isBlank()) {
            String[] parts = sort.split(",");
            if (!allowedFields.contains(parts[0].trim())) {
                throw new ValidationFailedException("Unsupported sort field", Map.of("sort", "Allowed: " + String.join(", ", allowedFields)));
            }
            field = parts[0].trim();
            if (parts.length > 1) {
                dir = "asc".equalsIgnoreCase(parts[1].trim()) ? Sort.Direction.ASC : Sort.Direction.DESC;
            }
        }
        return PageRequest.of(Math.max(page, 0), Math.min(Math.max(size, 1), MAX_SIZE),
                Sort.by(dir, field).and(Sort.by(Sort.Direction.DESC, "id")));
    }

    /** Builds a safe LIKE pattern (lower-cased, wildcards escaped; use escape char '\\'). */
    public static String likePattern(String q) {
        String s = q.trim().toLowerCase().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
        return "%" + s + "%";
    }
}
