# Security Policy
## Supported Versions
| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |
## Reporting a Vulnerability
**Do not file a public GitHub issue for security vulnerabilities.**
Open a private security advisory on GitHub via **Security → Report a vulnerability**.
Include: description, steps to reproduce, potential impact, suggested fix.
You will receive an acknowledgement within 48 hours and a full response within 7 days.
## Security Design
- **Permission gates** - every tool call passes through `actions/permissions.py`
- **Risk classification** - tools rated LOW / MEDIUM / HIGH / CRITICAL
- **Audit logging** - all tool executions logged with timestamps
- **Secret redaction** - API keys stripped from all log output
- **Network sandboxing** - network tool access is scoped and auditable
- **Local-only by default** - server binds `127.0.0.1` unless `--lan` passed
## What to Report
- Prompt injection bypassing permission gates
- Tool execution escaping its sandbox
- Log output leaking API keys or secrets
- Auth bypass in the web API (`web.py`)
- Path traversal in the static file server
