package com.nexusai.common.config;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/** SEC-06: in prod, refuse to start with missing or dev-default secrets. */
@Component
@Profile("prod")
public class ProdConfigValidator {
    private static final Logger log = LoggerFactory.getLogger(ProdConfigValidator.class);
    private final NexusProperties props;
    private final String dbPassword;

    public ProdConfigValidator(NexusProperties props, @Value("${spring.datasource.password:}") String dbPassword) {
        this.props = props;
        this.dbPassword = dbPassword;
    }

    @PostConstruct
    void validate() {
        require(props.jwt().secret() != null && props.jwt().secret().length() >= 32 && !props.jwt().secret().contains("dev-only"),
                "JWT_SECRET must be set (>= 32 chars, not a dev default)");
        require(props.internalApiKey() != null && props.internalApiKey().length() >= 16 && !props.internalApiKey().contains("dev-only"),
                "INTERNAL_API_KEY must be set (>= 16 chars, not a dev default)");
        require(dbPassword != null && !dbPassword.isBlank() && !"nexus_dev".equals(dbPassword), "POSTGRES_PASSWORD must be set and not the dev default");
        if (!props.cookieSecure()) {
            log.warn("COOKIE_SECURE is false in prod: refresh cookies will be sent over plain HTTP");
        }
    }

    private static void require(boolean ok, String message) {
        if (!ok) throw new IllegalStateException("Invalid production configuration: " + message);
    }
}
