# YTUSocial

YTUSocial is an independent, student-founded campus social platform built to bring university life into one product: people, communities, clubs, events, conversations and useful campus content.

**Website:** https://ytusocial.com  
**Contact:** ali@ytusocial.com

> YTUSocial is an independent student project and is not an official service of Yıldız Technical University.

## What the product does

YTUSocial combines the core parts of campus life in a single experience:

- Social feed, profiles, follows, likes and saved posts
- Direct messaging, inbox and real-time presence
- Stories / short-form campus content
- Clubs, communities and campus discovery
- Notes and student-oriented resources
- Notifications and trending hashtags
- Admin and moderation workflows
- Email verification and account recovery flows

## AI roadmap

The next product phase is focused on AI-assisted campus discovery and safer community operations. Planned work includes:

- Claude-powered discovery across clubs, events and campus content
- Context-aware moderation assistance for reports and community safety
- Concise summaries for events, clubs and long campus posts
- Helpful, grounded student assistance inside the product

These AI features are under development; the existing repository contains the current core social platform.

## Tech stack

- Python / Flask
- SQLAlchemy + PostgreSQL
- Flask-Login, Flask-WTF and Flask-Migrate / Alembic
- Flask-SocketIO
- Jinja templates, JavaScript and CSS
- SendGrid for transactional email
- GitHub Actions for deployment

## Local development

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it using the command for your operating system, then install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure local secrets

Copy the example configuration to a local, ignored file:

```bash
mkdir -p instance
cp important.local.env.example instance/important.local.env
```

At minimum, set a real PostgreSQL `DATABASE_URL` and a strong `SECRET_KEY`.

Never commit production credentials, API keys, user databases, logs or uploaded user content.

### 3. Run the app

```bash
python app.py
```

The development server listens on port `5002` by default.

## Repository hygiene

Runtime data and secrets are intentionally excluded from version control. User uploads, local databases, logs, generated caches and environment files must stay outside Git history.

If a credential has ever been committed publicly, deleting the file is not enough: rotate/revoke that credential because it may still exist in Git history or third-party caches.

## Security

Please do not open public issues containing vulnerabilities, credentials or personal data. See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

## Status

YTUSocial is an early-stage, bootstrapped product under active development.
