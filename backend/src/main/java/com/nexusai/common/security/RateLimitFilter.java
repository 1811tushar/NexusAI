package com.nexusai.common.security;

import com.nexusai.common.config.NexusProperties;
import com.nexusai.common.exception.ErrorCode;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.ConsumptionProbe;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * In-memory Bucket4j limiter (single backend instance, no Redis). Auth endpoints are limited per client IP,
 * upload and investigation start per user. Idle buckets are evicted lazily.
 */
public class RateLimitFilter extends OncePerRequestFilter {
    private static final long IDLE_NANOS = TimeUnit.MINUTES.toNanos(10);
    private static final long EVICT_EVERY_NANOS = TimeUnit.MINUTES.toNanos(5);

    private record Rule(String name, int perMin, boolean perUser) { }
    private static final class Entry {
        final Bucket bucket;
        volatile long lastUsed = System.nanoTime();
        Entry(Bucket b) { this.bucket = b; }
    }

    private final NexusProperties.RateLimit limits;
    private final JsonErrorWriter writer;
    private final ConcurrentMap<String, Entry> buckets = new ConcurrentHashMap<>();
    private final AtomicLong lastEvict = new AtomicLong(System.nanoTime());

    public RateLimitFilter(NexusProperties.RateLimit limits, JsonErrorWriter writer) {
        this.limits = limits;
        this.writer = writer;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ServletException, IOException {
        Rule rule = match(req);
        if (rule == null) {
            chain.doFilter(req, res);
            return;
        }
        evictIdle();
        String key = rule.name + ":" + (rule.perUser ? userOrIp(req) : req.getRemoteAddr());
        Entry e = buckets.computeIfAbsent(key, k -> new Entry(newBucket(rule.perMin)));
        e.lastUsed = System.nanoTime();
        ConsumptionProbe probe = e.bucket.tryConsumeAndReturnRemaining(1);
        if (probe.isConsumed()) {
            chain.doFilter(req, res);
        } else {
            long wait = Math.max(1, TimeUnit.NANOSECONDS.toSeconds(probe.getNanosToWaitForRefill()));
            res.setHeader("Retry-After", Long.toString(wait));
            writer.write(res, ErrorCode.RATE_LIMITED, "Too many requests. Try again in " + wait + " seconds.");
        }
    }

    private Rule match(HttpServletRequest req) {
        if (!"POST".equals(req.getMethod())) return null;
        String p = req.getRequestURI();
        if (p.length() > 1 && p.endsWith("/")) p = p.substring(0, p.length() - 1);
        if (p.equals(RateLimitPolicy.PATH_LOGIN) || p.equals(RateLimitPolicy.PATH_REGISTER) || p.equals(RateLimitPolicy.PATH_REFRESH)) {
            return new Rule("auth", limits.authPerMin(), false);
        }
        if (p.equals(RateLimitPolicy.PATH_UPLOAD)) return new Rule("upload", limits.uploadPerMin(), true);
        if (p.equals(RateLimitPolicy.PATH_INVESTIGATION_START)) return new Rule("invstart", limits.investigationStartPerMin(), true);
        return null;
    }

    private static String userOrIp(HttpServletRequest req) {
        Authentication a = SecurityContextHolder.getContext().getAuthentication();
        if (a != null && a.getPrincipal() instanceof AuthenticatedUser u) return "u" + u.id();
        return "ip" + req.getRemoteAddr();
    }

    private static Bucket newBucket(int perMin) {
        int n = Math.max(1, perMin);
        return Bucket.builder().addLimit(l -> l.capacity(n).refillGreedy(n, Duration.ofMinutes(1))).build();
    }

    private void evictIdle() {
        long now = System.nanoTime();
        long last = lastEvict.get();
        if (now - last > EVICT_EVERY_NANOS && lastEvict.compareAndSet(last, now)) {
            buckets.entrySet().removeIf(en -> now - en.getValue().lastUsed > IDLE_NANOS);
        }
    }
}
