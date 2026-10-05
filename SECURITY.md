# Security Policy

## Supported versions

Security fixes are applied to the main branch.

## Reporting a vulnerability

Do not disclose credentials, API keys, database connection strings, or exploitable details in a public issue.

For a private report, contact the repository owner through GitHub.

Please include:
- affected component or endpoint
- reproducible steps
- expected and observed behavior
- impact assessment
- relevant logs with secrets removed

## Production secrets

Never commit:
- MongoDB credentials
- JWT secrets
- AI provider API keys
- live-market provider credentials
- deployment tokens

Use deployment-platform secret storage or environment variables.
