package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;

public record AgentStepDTO(int seq, String type, JsonNode payload, Instant createdAt) { }
