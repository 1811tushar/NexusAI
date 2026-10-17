package com.nexusai.common.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nexusai.common.dto.ApiError;
import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.exception.ErrorCode;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.slf4j.MDC;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;

/** Writes the ApiResponse error envelope from servlet-level code (filters, entry points) where @ControllerAdvice does not run. */
@Component
public class JsonErrorWriter {
    private final ObjectMapper mapper;
    public JsonErrorWriter(ObjectMapper mapper) { this.mapper = mapper; }

    public void write(HttpServletResponse res, ErrorCode code, String message) throws IOException {
        res.setStatus(code.httpStatus());
        res.setContentType(MediaType.APPLICATION_JSON_VALUE);
        res.setCharacterEncoding("UTF-8");
        mapper.writeValue(res.getOutputStream(), ApiResponse.fail(new ApiError(code, message, null, MDC.get(RequestIdFilter.MDC_KEY))));
    }
}
