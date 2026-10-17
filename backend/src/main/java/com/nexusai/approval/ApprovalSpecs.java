package com.nexusai.approval;

import com.nexusai.investigation.Investigation;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import jakarta.persistence.criteria.Subquery;
import java.util.ArrayList;
import java.util.List;
import org.springframework.data.jpa.domain.Specification;

final class ApprovalSpecs {
    private ApprovalSpecs() { }

    /** ownerId == null means "all investigations" (approver/admin). */
    static Specification<Approval> scoped(Long ownerId, ApprovalStatus status) {
        return (root, query, cb) -> {
            List<Predicate> ps = new ArrayList<>();
            if (status != null) ps.add(cb.equal(root.get("status"), status));
            if (ownerId != null) {
                Subquery<Long> sq = query.subquery(Long.class);
                Root<Investigation> ir = sq.from(Investigation.class);
                sq.select(ir.get("id")).where(cb.equal(ir.get("userId"), ownerId));
                ps.add(root.get("investigationId").in(sq));
            }
            return cb.and(ps.toArray(new Predicate[0]));
        };
    }
}
