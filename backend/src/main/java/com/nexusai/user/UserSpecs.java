package com.nexusai.user;

import com.nexusai.common.util.PageUtil;
import jakarta.persistence.criteria.Predicate;
import java.util.ArrayList;
import java.util.List;
import org.springframework.data.jpa.domain.Specification;

final class UserSpecs {
    private UserSpecs() { }

    static Specification<User> search(String q, Role role) {
        return (root, query, cb) -> {
            List<Predicate> ps = new ArrayList<>();
            if (q != null && !q.isBlank()) {
                String p = PageUtil.likePattern(q);
                ps.add(cb.or(cb.like(cb.lower(root.get("email")), p, '\\'), cb.like(cb.lower(root.get("displayName")), p, '\\')));
            }
            if (role != null) ps.add(cb.equal(root.get("role"), role));
            return cb.and(ps.toArray(new Predicate[0]));
        };
    }
}
