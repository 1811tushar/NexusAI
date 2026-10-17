package com.nexusai.investigation;

import com.nexusai.common.util.PageUtil;
import jakarta.persistence.criteria.Predicate;
import java.util.ArrayList;
import java.util.List;
import org.springframework.data.jpa.domain.Specification;

final class InvestigationSpecs {
    private InvestigationSpecs() { }

    /** ownerId == null means every owner (approver/admin without ?mine=true). */
    static Specification<Investigation> filter(Long ownerId, InvestigationStatus status, String q) {
        return (root, query, cb) -> {
            List<Predicate> ps = new ArrayList<>();
            if (ownerId != null) ps.add(cb.equal(root.get("userId"), ownerId));
            if (status != null) ps.add(cb.equal(root.get("status"), status));
            if (q != null && !q.isBlank()) ps.add(cb.like(cb.lower(root.get("question")), PageUtil.likePattern(q), '\\'));
            return cb.and(ps.toArray(new Predicate[0]));
        };
    }
}
