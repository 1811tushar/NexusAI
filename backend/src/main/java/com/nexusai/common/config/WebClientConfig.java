package com.nexusai.common.config;

import io.netty.channel.ChannelOption;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

/** WebClient used ONLY by AiServiceClient. Adds the internal API key to every call. */
@Configuration
public class WebClientConfig {
    @Bean
    public WebClient aiWebClient(WebClient.Builder builder, NexusProperties props) {
        HttpClient http = HttpClient.create().option(ChannelOption.CONNECT_TIMEOUT_MILLIS, props.ai().connectTimeoutMs());
        return builder
                .baseUrl(props.ai().url())
                .defaultHeader("X-Internal-API-Key", props.internalApiKey())
                .clientConnector(new ReactorClientHttpConnector(http))
                .codecs(c -> c.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
                .build();
    }
}
