package com.nexusai.common.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.nexusai.common.exception.ErrorCode;
import java.util.Map;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record ApiError(ErrorCode code, String message, Map<String, String> details, String requestId) { }
