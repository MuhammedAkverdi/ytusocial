# Security Policy

## Reporting a vulnerability

Please do **not** report security vulnerabilities in a public GitHub issue.

Send security reports to **ali@ytusocial.com** with:

- a short description of the issue,
- affected endpoint or component,
- reproduction steps,
- potential impact,
- and any suggested mitigation.

Please avoid accessing, modifying or downloading data that does not belong to you while testing.

## Secrets and credentials

Credentials, API keys, database URLs, private keys and production environment files must never be committed to this repository.

If a credential is accidentally committed, treat it as compromised even after the file is deleted: revoke or rotate it immediately, then remove it from active Git history where practical.

## Personal and runtime data

User databases, logs, messages, uploaded media and other runtime-generated data are not source code and should remain outside Git version control.
