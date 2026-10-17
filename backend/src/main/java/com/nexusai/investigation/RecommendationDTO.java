package com.nexusai.investigation;

import com.nexusai.approval.Risk;

public record RecommendationDTO(String id, String text, Risk risk, String actionKey) { }
