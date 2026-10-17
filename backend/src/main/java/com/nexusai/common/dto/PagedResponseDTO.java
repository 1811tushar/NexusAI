package com.nexusai.common.dto;

import java.util.List;
import java.util.function.Function;
import org.springframework.data.domain.Page;

public record PagedResponseDTO<T>(List<T> items, int page, int size, long totalItems, int totalPages) {
    public static <E, T> PagedResponseDTO<T> from(Page<E> page, Function<E, T> mapper) {
        return new PagedResponseDTO<>(page.getContent().stream().map(mapper).toList(), page.getNumber(), page.getSize(),
                page.getTotalElements(), page.getTotalPages());
    }
}
