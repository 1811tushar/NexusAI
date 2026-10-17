package com.nexusai.document;

public record SearchResultDTO(Long chunkId, Long documentId, String documentTitle, Integer page, String section, String snippet, double score) {
    public SearchResultDTO withTitle(String title) {
        return new SearchResultDTO(chunkId, documentId, title, page, section, snippet, score);
    }
}
