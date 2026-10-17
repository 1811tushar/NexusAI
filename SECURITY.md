# Security policy

Do not report vulnerabilities in public issues. Contact the repository maintainers privately through GitHub Security Advisories.

## Operational controls
- Never commit `.env`, credentials, production dumps, or real customer data.
- Rotate `JWT_SECRET`, `INTERNAL_API_KEY`, database passwords, and provider keys after exposure.
- Python is an internal-only service; never publish port 8000.
- Use synthetic data with third-party LLM, web-search, and tracing providers. Enable Ollama for local-only processing.
- AI SQL access is restricted to `ai_readonly`, AST-validated, limited, and timed out.
- High-risk actions are simulated and require a stored human approval; Python cannot execute them.
- Report suspected security incidents promptly and preserve relevant logs.
