package com.nexusai.common.exception;

import com.nexusai.common.dto.ApiError;
import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.security.RequestIdFilter;
import jakarta.validation.ConstraintViolationException;
import java.util.LinkedHashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.ServletRequestBindingException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.MultipartException;
import org.springframework.web.multipart.support.MissingServletRequestPartException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/** BE-PL-01: every failure becomes an ApiResponse envelope; unknown errors become a vague 500 with a request id and no stack trace. */
@RestControllerAdvice
public class GlobalExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> business(BusinessException e) {
        if (e.getCode().httpStatus() >= 500) log.warn("{}: {}", e.getCode(), e.getMessage());
        return build(e.getCode(), e.getMessage(), e.getDetails());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> invalidBody(MethodArgumentNotValidException e) {
        Map<String, String> details = new LinkedHashMap<>();
        e.getBindingResult().getFieldErrors().forEach(fe -> details.putIfAbsent(fe.getField(), fe.getDefaultMessage()));
        e.getBindingResult().getGlobalErrors().forEach(ge -> details.putIfAbsent(ge.getObjectName(), ge.getDefaultMessage()));
        return build(ErrorCode.VALIDATION_FAILED, "Validation failed", details);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ApiResponse<Void>> constraint(ConstraintViolationException e) {
        Map<String, String> details = new LinkedHashMap<>();
        e.getConstraintViolations().forEach(v -> {
            String path = v.getPropertyPath().toString();
            details.putIfAbsent(path.substring(path.lastIndexOf('.') + 1), v.getMessage());
        });
        return build(ErrorCode.VALIDATION_FAILED, "Validation failed", details);
    }

    @ExceptionHandler(MissingServletRequestPartException.class)
    public ResponseEntity<ApiResponse<Void>> missingPart(MissingServletRequestPartException e) {
        return build(ErrorCode.VALIDATION_FAILED, "Missing required part", Map.of(e.getRequestPartName(), "is required"));
    }

    @ExceptionHandler(MissingServletRequestParameterException.class)
    public ResponseEntity<ApiResponse<Void>> missingParam(MissingServletRequestParameterException e) {
        return build(ErrorCode.VALIDATION_FAILED, "Missing required parameter", Map.of(e.getParameterName(), "is required"));
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ApiResponse<Void>> typeMismatch(MethodArgumentTypeMismatchException e) {
        return build(ErrorCode.VALIDATION_FAILED, "Invalid parameter", Map.of(e.getName(), "has an invalid value"));
    }

    @ExceptionHandler({HttpMessageNotReadableException.class, ServletRequestBindingException.class, MultipartException.class})
    public ResponseEntity<ApiResponse<Void>> unreadable(Exception e) {
        return build(ErrorCode.VALIDATION_FAILED, "Malformed request", null);
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ApiResponse<Void>> tooLarge(MaxUploadSizeExceededException e) {
        return build(ErrorCode.FILE_TOO_LARGE, "The file is larger than the allowed upload size", null);
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ApiResponse<Void>> denied(AccessDeniedException e) {
        return build(ErrorCode.FORBIDDEN, "You do not have permission to do this", null);
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiResponse<Void>> noResource(NoResourceFoundException e) {
        return build(ErrorCode.NOT_FOUND, "Resource not found", null);
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<ApiResponse<Void>> method(HttpRequestMethodNotSupportedException e) {
        // not in the contract catalogue: nearest code, real HTTP status
        return ResponseEntity.status(405).contentType(org.springframework.http.MediaType.APPLICATION_JSON).body(ApiResponse.fail(new ApiError(ErrorCode.VALIDATION_FAILED, "Method not allowed", null, rid())));
    }

    @ExceptionHandler(HttpMediaTypeNotSupportedException.class)
    public ResponseEntity<ApiResponse<Void>> mediaType(HttpMediaTypeNotSupportedException e) {
        return ResponseEntity.status(415).contentType(org.springframework.http.MediaType.APPLICATION_JSON).body(ApiResponse.fail(new ApiError(ErrorCode.UNSUPPORTED_FILE_TYPE, "Unsupported content type", null, rid())));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> unexpected(Exception e) {
        log.error("Unhandled exception", e);
        return build(ErrorCode.INTERNAL_ERROR, "An unexpected error occurred", null);
    }

    private static ResponseEntity<ApiResponse<Void>> build(ErrorCode code, String message, Map<String, String> details) {
        return ResponseEntity.status(code.httpStatus()).contentType(org.springframework.http.MediaType.APPLICATION_JSON).body(ApiResponse.fail(new ApiError(code, message, details, rid())));
    }

    private static String rid() { return MDC.get(RequestIdFilter.MDC_KEY); }
}
