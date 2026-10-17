package com.nexusai.auth;

import com.nexusai.common.config.NexusProperties;
import java.time.Duration;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

@Component
public class RefreshCookieFactory {
    public static final String NAME = "nx_refresh";
    public static final String PATH = "/api/auth";
    private final NexusProperties props;
    public RefreshCookieFactory(NexusProperties props) { this.props = props; }

    public ResponseCookie issue(String rawToken) {
        return base(rawToken).maxAge(Duration.ofDays(props.jwt().refreshDays())).build();
    }
    public ResponseCookie clear() { return base("").maxAge(Duration.ZERO).build(); }

    private ResponseCookie.ResponseCookieBuilder base(String value) {
        return ResponseCookie.from(NAME, value).httpOnly(true).secure(props.cookieSecure()).path(PATH).sameSite("Lax");
    }
}
