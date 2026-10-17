package com.nexusai.investigation;

import java.util.List;

public record ClaimDTO(Long id, String text, ClaimStatus status, double confidence, boolean isKey, List<String> evidenceKeys) { }
