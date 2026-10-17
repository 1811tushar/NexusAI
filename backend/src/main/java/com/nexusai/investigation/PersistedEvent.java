package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;

/** An event that has been committed to agent_steps with its Spring-assigned sequence number. */
public record PersistedEvent(int seq, String type, JsonNode payload) { }
