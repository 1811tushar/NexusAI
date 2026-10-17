package com.nexusai.ai;

/** One SSE frame from the Python service: event name + raw JSON data string. */
public record AiEvent(String type, String data) { }
