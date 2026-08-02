# Security Policy

ArchiveLens stores platform login state and may connect to private infrastructure such as PostgreSQL, Redis, and webhook endpoints. Treat deployments as sensitive even when the code repository is public.

## Supported Versions

The project is currently pre-1.0. Security fixes are accepted on the default branch.

## Reporting a Vulnerability

Please do not open a public issue with secrets, cookies, session files, or exploit details. Instead, contact the maintainer privately through the GitHub profile associated with this repository.

When reporting, include:

- A concise description of the issue.
- Steps to reproduce in a local or test environment.
- The affected component, such as backend API, platform adapter, worker, deployment config, or frontend.
- Any relevant logs with secrets redacted.

## Sensitive Data

Never commit:

- `.env` or `.env.prod`
- Platform session files under `auth/`, `.auth/`, or `data/auth/`
- Downloaded media archives under `data/media/`
- PostgreSQL, Redis, webhook, or admin tokens

The repository includes `.env.example` and `.env.prod.example` for safe configuration templates.
