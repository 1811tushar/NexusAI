package com.nexusai.common.security;

import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

/** Reads "Authorization: Bearer", validates the JWT and sets the principal (role claim becomes ROLE_*). Never throws. */
public class JwtAuthFilter extends OncePerRequestFilter {
    public static final String ATTR_TOKEN_EXPIRED = "nexus.tokenExpired";
    private final JwtUtil jwt;

    public JwtAuthFilter(JwtUtil jwt) { this.jwt = jwt; }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ServletException, IOException {
        String header = req.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            try {
                AuthenticatedUser u = jwt.parse(header.substring(7).trim());
                var auth = new UsernamePasswordAuthenticationToken(u, null, List.of(new SimpleGrantedAuthority("ROLE_" + u.role().name())));
                SecurityContextHolder.getContext().setAuthentication(auth);
            } catch (ExpiredJwtException e) {
                req.setAttribute(ATTR_TOKEN_EXPIRED, Boolean.TRUE);
            } catch (JwtException | IllegalArgumentException e) {
                // invalid token: stays unauthenticated, the entry point answers 401
            }
        }
        chain.doFilter(req, res);
    }
}
