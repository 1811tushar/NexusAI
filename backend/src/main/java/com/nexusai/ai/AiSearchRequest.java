package com.nexusai.ai;

import java.util.List;

public record AiSearchRequest(String query, String mode, int k, List<Long> documentIds) { }
