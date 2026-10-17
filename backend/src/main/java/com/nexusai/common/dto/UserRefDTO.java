package com.nexusai.common.dto;

/** {id, displayName} reference used inside several DTOs (owner, decidedBy, uploadedBy). */
public record UserRefDTO(Long id, String displayName) { }
