package com.nexusai.document;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.exception.ValidationFailedException;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/search")
public class SearchController {
    private static final Set<String> MODES = Set.of("HYBRID", "VECTOR", "KEYWORD");
    private final DocumentService service;
    public SearchController(DocumentService service) { this.service = service; }

    @GetMapping
    public ApiResponse<List<SearchResultDTO>> search(@RequestParam String q, @RequestParam(defaultValue = "HYBRID") String mode,
                                                     @RequestParam(defaultValue = "8") int k) {
        if (q.isBlank() || q.length() > 500) throw new ValidationFailedException("Invalid query", Map.of("q", "must be 1-500 characters"));
        String m = mode.toUpperCase(Locale.ROOT);
        if (!MODES.contains(m)) throw new ValidationFailedException("Invalid mode", Map.of("mode", "must be HYBRID, VECTOR or KEYWORD"));
        return ApiResponse.ok(service.search(q, m, k));
    }
}
