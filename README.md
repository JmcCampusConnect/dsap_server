# DASP Backend

A production-oriented Django backend for the Digital Academic Service Platform, covering local setup, architecture conventions, API design, background jobs, security, and delivery workflow.

![Django](https://img.shields.io/badge/Django-5+-092E20?logo=django)
![Django REST Framework](https://img.shields.io/badge/DRF-3.15+-ff1709?logo=django)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql)
![Celery](https://img.shields.io/badge/Celery-5+-37814A?logo=celery)

> This guide complements the frontend documentation and database design references for the full DASP stack.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Django Architecture & Patterns](#django-architecture--patterns)
- [API Design](#api-design)
- [Background Jobs (Celery)](#background-jobs-celery)
- [Security](#security)
- [Testing](#testing)
- [Git Workflow](#git-workflow)
- [CI/CD Pipeline](#cicd-pipeline)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Overview

This guide covers everything needed to build and operate the DASP backend, including local setup, project structure, Django/DRF conventions, API design, background jobs, security, and the Git workflow. Pair it with the frontend developer guide and the database design document when working across the stack.

---

## Prerequisites

- Python 3.12 or later
- PostgreSQL 15+
- Redis (Celery broker and result backend)
- Git

---

## Getting Started

```bash
# Clone and enter the backend
git clone <repo-url>
cd dasp-server

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements/dev.txt

# Copy environment variables and fill in the values
cp .env.example .env

# Apply migrations and create an admin account
python manage.py migrate
python manage.py createsuperuser

# Start the API server
python manage.py runserver
```

In a separate terminal, start the Celery worker:

```bash
celery -A config worker -l info
```

If you use scheduled tasks, also start the Celery beat scheduler:

```bash
celery -A config beat -l info
```

The API runs at `http://localhost:8000/api/v1` by default.

---

## Environment Variables
 
Create a `.env` file with values such as:

```env
DEBUG=True
SECRET_KEY=change-me
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgres://dasp:dasp@localhost:5432/dasp

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

JWT_ACCESS_TOKEN_LIFETIME_MIN=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

CORS_ALLOWED_ORIGINS=http://localhost:5173

SMS_GATEWAY_API_KEY=
EMAIL_HOST=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

### Convention

Never commit `.env`. Secrets such as `SECRET_KEY`, database credentials, and gateway API keys should be injected at deploy time through your hosting platform's secrets manager rather than stored in the repository.

---

## Project Structure

```text
dasp-server/
├── config/                       # Django project settings
│   ├── settings/
│   │   ├── base.py               # Base settings
│   │   ├── dev.py                # Development settings
│   │   ├── staging.py            # Staging settings
│   │   └── production.py         # Production settings
│   ├── urls.py                   # Main URL configuration
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/                         # Django applications
│   ├── accounts/                 # Users, roles, auth (OTP, JWT)
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── permissions.py
│   │   └── tests/
│   │
│   ├── students/                 # Student master data, ERP sync
│   ├── departments/              # ServiceDepartment, AcademicDepartment
│   ├── services/                 # Service catalogue, fields, documents
│   ├── workflow/                 # Workflow steps, routing engine
│   ├── requests/                 # Request lifecycle, field values
│   ├── documents/                # Upload, virus scan, storage
│   ├── payments/                 # Gateway integration, webhooks
│   ├── notifications/            # Templates, SMS/email (Celery)
│   ├── audit/                    # AuditLog
│   └── reports/                  # Report queries, PDF/Excel export
│
├── common/                       # Shared utilities
│   ├── base_models.py            # Abstract base model (created_at/updated_at)
│   ├── exceptions.py
│   ├── pagination.py
│   └── validators.py
│
├── celery_app/
│   ├── __init__.py
│   ├── celery.py
│   └── tasks.py
│
├── seeders/                      # Lightweight database seeders
│   ├── __init__.py
│   ├── runner.py
│   ├── role_seeder.py
│   └── user_seeder.py
│   └── ... (add more as needed)
│
├── tests/                        # Cross-app integration tests
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
│
└── manage.py
```

---

## Database Seeders

Use the seeder runner to populate the initial reference data needed for local development.

### Quick Start

```bash
cd dsap_server
python seeders/runner.py
```

Run a single seeder:

```bash
python seeders/runner.py role_seeder
python seeders/runner.py user_seeder
```

List available seeders:

```bash
python seeders/runner.py --list
```

### Adding a New Seeder

Create a new file in the `seeders/` folder, follow the existing `role_seeder.py` or `user_seeder.py` pattern, and register it in `seeders/runner.py`.

---

## Technology Stack

| Category | Technology | Version |
| --- | --- | --- |
| Language | Python | 3.12+ |
| Web framework | Django | 5+ |
| API framework | Django REST Framework | 3.15+ |
| Database | PostgreSQL | 15+ |
| Cache / broker | Redis | 7+ |
| Background jobs | Celery | 5+ |
| Auth | JWT (SimpleJWT) + OTP | Latest |
| WSGI/ASGI server | Gunicorn / Uvicorn | Latest |
| Testing | pytest-django + factory_boy | Latest |
| Linting / formatting | ruff, black | Latest |
| Type checking | mypy (optional, encouraged) | Latest |

---

## Django Architecture & Patterns

### App Structure

Each domain lives in its own app under `apps/`, following the same internal layout:

- `models.py` — one model per file for larger apps, otherwise a single module
- `serializers.py` — DRF serializers; keep validation logic here, not in views
- `views.py` — thin ViewSets/APIViews that delegate to services/selectors
- `permissions.py` — DRF permission classes implementing the role rules from the database design document
- `urls.py` — router registration for this app
- `tests/` — unit tests for this app's models, serializers, and views

### Model Conventions

```python
# common/base_models.py
class BaseModel(models.Model):
    """Abstract base adding standard audit columns to every model."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

- Every concrete model inherits `BaseModel` unless there is a documented reason not to (for example, `AuditLog`, which is deliberately append-only).
- Prefer explicit `related_name` on every `ForeignKey`.
- Business logic that spans multiple models belongs in a `services.py` module rather than in a model method or a view.

### Serializer Conventions

- Use one serializer per use case; a list serializer and a detail/write serializer are not the same thing if their fields differ.
- Validation that needs a database lookup belongs in `validate_<field>` or `validate()`, not in the view.
- Never expose internal fields such as `password_hash` or `raw_aadhar_no` through a default serializer; use explicit fields instead of `exclude`.

### Permissions (RBAC)

Every endpoint is protected by a DRF permission class that checks the caller's role and, where relevant, their `service_department_id` or `academic_department_id`, mirroring the access matrix in the database design document rather than relying on the frontend to hide a menu.

```python
# apps/requests/permissions.py
class IsServiceDepartmentStaffForRequest(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        return (
            user.role.name == "SERVICE_DEPT_STAFF"
            and obj.service.service_department_id == user.service_department_id
        )
```

---

## API Design

- Use RESTful, resource-oriented endpoints, versioned under `/api/v1/...`
- Use plural nouns for collections such as `/api/v1/requests/` and `/api/v1/students/`
- Apply pagination to every list endpoint (default size 20, maximum 100)
- Support filtering and search via query parameters, documented per endpoint

### Standard Error Envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields are invalid.",
    "details": {
      "mobile_number": ["This field is required."]
    }
  }
}
```

### HTTP Status Codes

| Code | Meaning |
| --- | --- |
| 200 | Success |
| 201 | Resource created |
| 204 | Success, no content (for example, delete) |
| 400 | Validation error |
| 401 | Not authenticated |
| 403 | Authenticated but not permitted |
| 404 | Resource not found |
| 409 | Conflict (for example, duplicate register number) |
| 429 | Rate limited |
| 500 | Unhandled server error |

---

## Background Jobs (Celery)

- Notifications, report generation, and PDF certificate rendering run as Celery tasks rather than inline in the request/response cycle.
- Every task is idempotent, so it is safe to retry without side effects such as duplicate notifications.
- Tasks retry with exponential backoff (default: 3 retries) and log failures to `AuditLog` where they affect a specific record.

```python
# apps/notifications/tasks.py
@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_notification(self, notification_id):
    try:
        notification = Notification.objects.get(pk=notification_id)
        # ... send via the configured channel ...
    except TransientGatewayError as exc:
        raise self.retry(exc=exc)
```

---

## Security

- Use JWT access and refresh tokens (SimpleJWT) with short-lived access tokens and refresh rotation enabled
- Validate and sanitize all input at the serializer layer; never trust client-supplied IDs without an object-permission check
- Keep the CORS allow-list restricted to known frontend origins per environment
- Protect sensitive fields such as `aadhar_no` and `password_hash` through encryption or hashing, and mask them in API responses by default
- Write each create, update, delete, login, and export action to `AuditLog`

---

## Git & GitHub Workflow Guide

This document is the single source of truth for how the team branches, commits, syncs, and merges code. Everyone should be able to follow it end to end.

### Golden Rule

- `main` is the production branch and should not be used for development.
- Do not commit directly to `main`.
- Do not create feature branches from `main`; always create them from `development`.
- `development` is the integration branch and should remain in a releasable state.
- Nobody commits directly to `development`.
- Every change comes in through a feature branch and a pull request (PR) to `development`.

### 1. Branching Model

- One branch per Jira ticket, always cut from an up-to-date `development`.
- Branch name format: `<TICKET-ID>-<short-kebab-case-description>-FE`.
- Here FE means Frontend and BE means Backend.

```bash
AF-121-implement-ui-for-login-screen-FE
AF-134-fix-otp-expiry-bug-BE
```

- Never reuse a branch for a second, unrelated ticket.

### 2. Starting Work on a Ticket

Always start from a fresh `development` branch to avoid merge drift.

```bash
git checkout development
git pull origin development
git checkout -b AF-121-implement-ui-for-login-screen
```

### 3. While You Work — Commit & Push

Commit in small, meaningful chunks rather than one large commit at the end. Prefix every commit message with the ticket ID so history and blame stay traceable to Jira.

```bash
git add <specific files>
git commit -m "AF-121: add login form skeleton"
```

First push on a new branch needs `-u` to link it to the remote:

```bash
git push -u origin AF-121-implement-ui-for-login-screen
```

Every push after that is just:

```bash
git push
```

### 4. Before Opening a PR — Sync With `development`

Do this every time, not only when GitHub warns you. `development` moves forward as other PRs get merged.

```bash
git checkout AF-121-implement-ui-for-login-screen
git fetch origin
git status
```

See what changed on each side before merging:

```bash
# Commits on development that you do not have yet
git log --oneline HEAD..origin/development

# Commits on your branch that development does not have yet
git log --oneline origin/development..HEAD
```

Bring `development` into your branch:

```bash
git merge origin/development
```

Use `merge`, not `rebase`, as the default for this team. Rebase rewrites commit history and requires a force-push, which is easy to get wrong and risky if a teammate has also pulled your branch.

If Git reports `Already up to date.` — great. If it reports conflicts, continue to the next section.

### 5. Resolving a Merge Conflict

When `git merge origin/development` stops with conflicts, work through them methodically:

```bash
git status
```

To see only the conflicted files:

```bash
git diff --name-only --diff-filter=U
```

For each conflicted file:

1. Open it in the editor and resolve the conflict markers.
2. Keep the correct combined result, then delete the `<<<<<<<`, `=======`, and `>>>>>>>` lines.
3. Save the file.

Once all conflicts are resolved:

```bash
git add <resolved files>
git status
git commit
git push
```

### 6. The "Branch Sat for 10 Days" Scenario — Direct Fix

If GitHub shows that the branch has conflicts or is out of date:

```bash
git checkout AF-121-implement-ui-for-login-screen
git fetch origin
git log --oneline HEAD..origin/development
git merge origin/development
```

If conflicts appear, resolve them as described above, then:

```bash
git add .
git commit
git push
```

GitHub re-evaluates the PR automatically after you push.

### 7. Opening the Pull Request

1. Push your branch.
2. On GitHub, set base to `development` and compare to your branch.
3. Title the PR with the ticket ID, for example: `AF-121: Implement UI for login screen`.
4. Fill in the PR description with the Jira ticket link, a short summary, and screenshots for UI changes.
5. Assign the project lead as reviewer.

### 8. Responding to Review Feedback

Push additional commits to the same branch and let the PR update automatically.

```bash
git add <changed files>
git commit -m "AF-121: address review comments — extract validation logic"
git push
```

### 10. Command Reference

| Command | What it does | When to use it |
| --- | --- | --- |
| `git checkout development && git pull origin development` | Update your local `development` branch | Before starting any new ticket |
| `git checkout -b <branch>` | Create and switch to a new branch | Starting a new ticket |
| `git status` | Show staged, unstaged, and conflicted files | Constantly |
| `git add <files>` | Stage changes for a commit | Before every commit |
| `git commit -m "TICKET: message"` | Record a commit | After staging changes |
| `git push -u origin <branch>` | Push a new branch and link it to the remote | First push on a new branch |
| `git push` | Push subsequent commits | Every push after the first |
| `git fetch origin` | Download the latest remote history without changing your files | Before syncing with `development` |
| `git log --oneline A..B` | List commits on `B` not on `A` | Checking what you are about to merge |
| `git merge origin/development` | Bring `development`'s changes into your branch | Before opening or updating a PR |
| `git diff --name-only --diff-filter=U` | List only conflicted file paths | Right after a merge reports conflicts |
| `git push --force-with-lease` | Safely overwrite your own remote branch | Only after rewriting commits mid-review |

### 11. Quick Troubleshooting

- If you committed straight to `development` by accident, tell the project lead immediately rather than trying to fix it alone.
- If you force-pushed and think you lost commits, inspect `git reflog`.
- If a PR shows conflicts, someone else likely merged into `development` after you branched. Go straight to Section 6.
- If you want to preview a merge before committing to it, run `git fetch origin` and `git diff HEAD origin/development`.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| The API fails to start | Verify the virtual environment is active and dependencies are installed |
| Database connection errors | Check PostgreSQL is running and `DATABASE_URL` is correct |
| Celery worker issues | Confirm Redis is available and `CELERY_BROKER_URL` is set properly |
| CORS errors in local development | Ensure `CORS_ALLOWED_ORIGINS` includes the frontend origin |

---

## Contributing

1. Create a feature branch from `development`
2. Implement the change following the standards in this guide
3. Run `ruff`, `black --check`, and `pytest` locally
4. Address review feedback and wait for approval

---


