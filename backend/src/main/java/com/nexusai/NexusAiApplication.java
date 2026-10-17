package com.nexusai;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class NexusAiApplication {
    public static void main(String[] args) { SpringApplication.run(NexusAiApplication.class, args); }
}
