package com.nexusai.document;

import com.nexusai.common.util.PageUtil;
import jakarta.persistence.criteria.Predicate;
import java.util.ArrayList;
import java.util.List;
import org.springframework.data.jpa.domain.Specification;

final class DocumentSpecs {
    private DocumentSpecs() { }

    static Specification<Document> filter(String q, DocumentStatus status, SourceType type) {
        return (root, query, cb) -> {
            List<Predicate> ps = new ArrayList<>();
            if (q != null && !q.isBlank()) {
                String p = PageUtil.likePattern(q);
                ps.add(cb.or(cb.like(cb.lower(root.get("title")), p, '\\'), cb.like(cb.lower(root.get("originalFilename")), p, '\\')));
            }
            if (status != null) ps.add(cb.equal(root.get("status"), status));
            if (type != null) ps.add(cb.equal(root.get("sourceType"), type));
            return cb.and(ps.toArray(new Predicate[0]));
        };
    }
}
