package com.nexusai.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nexusai.common.config.NexusProperties;
import com.nexusai.common.security.JsonErrorWriter;
import com.nexusai.common.security.RateLimitFilter;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class RateLimitFilterTest {
    private final RateLimitFilter filter = new RateLimitFilter(new NexusProperties.RateLimit(2, 20, 6), new JsonErrorWriter(new ObjectMapper()));

    private int call(String method, String uri, String ip) throws Exception {
        MockHttpServletRequest req = new MockHttpServletRequest(method, uri);
        req.setRemoteAddr(ip);
        MockHttpServletResponse res = new MockHttpServletResponse();
        filter.doFilter(req, res, new MockFilterChain());
        return res.getStatus();
    }

    @Test void limitsAuthEndpointsPerIpAndReturns429WithRetryAfter() throws Exception {
        assertThat(call("POST", "/api/auth/login", "1.1.1.1")).isEqualTo(200);
        assertThat(call("POST", "/api/auth/login", "1.1.1.1")).isEqualTo(200);
        MockHttpServletRequest req = new MockHttpServletRequest("POST", "/api/auth/login");
        req.setRemoteAddr("1.1.1.1");
        MockHttpServletResponse res = new MockHttpServletResponse();
        filter.doFilter(req, res, new MockFilterChain());
        assertThat(res.getStatus()).isEqualTo(429);
        assertThat(res.getHeader("Retry-After")).isNotNull();
        assertThat(res.getContentAsString()).contains("RATE_LIMITED");
        assertThat(call("POST", "/api/auth/login", "2.2.2.2")).isEqualTo(200);      // other client unaffected
    }

    @Test void ignoresUnrelatedRequests() throws Exception {
        for (int i = 0; i < 10; i++) assertThat(call("GET", "/api/documents", "3.3.3.3")).isEqualTo(200);
        for (int i = 0; i < 10; i++) assertThat(call("GET", "/api/auth/login", "3.3.3.3")).isEqualTo(200);
    }
}
