package com.nexusai.common.config;

import com.nexusai.common.exception.ErrorCode;
import com.nexusai.common.security.JsonErrorWriter;
import com.nexusai.common.security.JwtAuthFilter;
import com.nexusai.common.security.JwtUtil;
import com.nexusai.common.security.RateLimitFilter;
import jakarta.servlet.DispatcherType;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;
import org.springframework.web.cors.CorsConfigurationSource;

/**
 * Stateless JWT security. URL rules here are the coarse gate (401/403); ownership and visibility (404 on foreign ids,
 * "own only" deletes, self-approval) are enforced again in the services per contract section 2.
 * CSRF protection is off: all state-changing calls need a Bearer header; the only cookie-authenticated endpoints are
 * /api/auth/refresh and /logout, and the cookie is SameSite=Lax so cross-site POSTs do not carry it.
 */
@Configuration
public class SecurityConfig {

    @Bean
    public PasswordEncoder passwordEncoder(NexusProperties props) {
        return new BCryptPasswordEncoder(props.bcryptStrength());
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http, JwtUtil jwtUtil, JsonErrorWriter writer, NexusProperties props,
                                                   CorsConfigurationSource cors) throws Exception {
        JwtAuthFilter jwtFilter = new JwtAuthFilter(jwtUtil);
        RateLimitFilter rateLimitFilter = new RateLimitFilter(props.rateLimit(), writer);

        http.csrf(AbstractHttpConfigurer::disable)
            .cors(c -> c.configurationSource(cors))
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .httpBasic(AbstractHttpConfigurer::disable)
            .formLogin(AbstractHttpConfigurer::disable)
            .logout(AbstractHttpConfigurer::disable)
            .headers(h -> {
                h.frameOptions(f -> f.deny());
                h.contentTypeOptions(Customizer.withDefaults());
                h.referrerPolicy(r -> r.policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.NO_REFERRER));
                if (!props.docsPublic()) {
                    h.contentSecurityPolicy(csp -> csp.policyDirectives("default-src 'none'; frame-ancestors 'none'"));
                }
            })
            .exceptionHandling(e -> e
                .authenticationEntryPoint((req, res, ex) -> {
                    boolean expired = req.getAttribute(JwtAuthFilter.ATTR_TOKEN_EXPIRED) != null;
                    writer.write(res, expired ? ErrorCode.TOKEN_EXPIRED : ErrorCode.UNAUTHENTICATED,
                            expired ? "Access token expired" : "Authentication required");
                })
                .accessDeniedHandler((req, res, ex) -> writer.write(res, ErrorCode.FORBIDDEN, "You do not have permission to do this")))
            .authorizeHttpRequests(a -> {
                // Backend B: SseEmitter completes through an ASYNC dispatch that carries no Authorization header; without this the stream would 401 at the end.
                a.dispatcherTypeMatchers(DispatcherType.ASYNC, DispatcherType.ERROR).permitAll();
                a.requestMatchers(HttpMethod.OPTIONS, "/**").permitAll();
                a.requestMatchers(HttpMethod.POST, "/api/auth/register", "/api/auth/login", "/api/auth/refresh", "/api/auth/logout").permitAll();
                a.requestMatchers("/actuator/health", "/actuator/health/**").permitAll();
                // Prometheus is scraped on the internal network only: nginx proxies /api only, never /actuator.
                a.requestMatchers("/actuator/prometheus", "/actuator/info").permitAll();
                if (props.docsPublic()) {
                    a.requestMatchers("/v3/api-docs/**", "/swagger-ui/**", "/swagger-ui.html").permitAll();
                } else {
                    a.requestMatchers("/v3/api-docs/**", "/swagger-ui/**", "/swagger-ui.html").hasRole("ADMIN");
                }
                a.requestMatchers("/api/admin/**", "/api/eval/**").hasRole("ADMIN");
                a.requestMatchers(HttpMethod.POST, "/api/documents", "/api/documents/*/reindex").hasAnyRole("ADMIN", "ANALYST");
                a.requestMatchers(HttpMethod.DELETE, "/api/documents/*").hasAnyRole("ADMIN", "ANALYST");
                a.requestMatchers(HttpMethod.POST, "/api/approvals/*/decision").hasAnyRole("APPROVER", "ADMIN");
                a.requestMatchers(HttpMethod.POST, "/api/investigations", "/api/investigations/*/cancel").hasAnyRole("ADMIN", "ANALYST");
                a.anyRequest().authenticated();
            })
            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)
            .addFilterAfter(rateLimitFilter, JwtAuthFilter.class);
        return http.build();
    }
}
