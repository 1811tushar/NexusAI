package com.nexusai.user;

import com.nexusai.common.config.NexusProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/** Creates the first ADMIN from ADMIN_EMAIL/ADMIN_PASSWORD, only if no admin exists. No default password exists in code. */
@Component
public class AdminBootstrap implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(AdminBootstrap.class);
    private final UserRepository users;
    private final PasswordEncoder encoder;
    private final NexusProperties props;

    public AdminBootstrap(UserRepository users, PasswordEncoder encoder, NexusProperties props) {
        this.users = users;
        this.encoder = encoder;
        this.props = props;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        String email = props.admin().email();
        String password = props.admin().password();
        if (email == null || email.isBlank() || password == null || password.isBlank()) {
            log.info("No bootstrap admin configured (ADMIN_EMAIL / ADMIN_PASSWORD unset)");
            return;
        }
        if (users.existsByRole(Role.ADMIN)) return;
        PasswordPolicy.validate(password, "ADMIN_PASSWORD");   // fails startup on a weak bootstrap password
        User u = new User();
        u.setEmail(UserService.normalizeEmail(email));
        u.setDisplayName("Administrator");
        u.setRole(Role.ADMIN);
        u.setPasswordHash(encoder.encode(password));
        users.save(u);
        log.info("Bootstrap ADMIN created");
    }
}
