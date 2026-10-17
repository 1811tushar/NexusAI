package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;

public record EvidenceDTO(String evidenceKey, EvidenceKind kind, String title, String snippet, JsonNode source, JsonNode data, JsonNode chart,
                          Double score, Instant createdAt) { }
