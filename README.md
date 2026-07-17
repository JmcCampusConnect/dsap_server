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
├── tests/                        # Cross-app integration tests
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
│
└── manage.py
```

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
- Require OTP verification for login and for sensitive actions such as changing a mobile number
- Validate and sanitize all input at the serializer layer; never trust client-supplied IDs without an object-permission check
- Keep the CORS allow-list restricted to known frontend origins per environment
- Apply rate limiting to auth and OTP endpoints to reduce brute-force and SMS-bombing risks
- Protect sensitive fields such as `aadhar_no` and `password_hash` through encryption or hashing, and mask them in API responses by default
- Write each create, update, delete, login, and export action to `AuditLog`

---

## Testing

```bash
# Run the full suite
pytest

# With coverage
pytest --cov=apps --cov-report=term-missing

# A single app
pytest apps/requests
```

- Use `factory_boy` factories instead of hand-built fixtures for model instances
- Test permission classes explicitly; a role that should receive a `403` must be asserted, not assumed
- Target 85% line coverage on `apps/` before merging a feature branch

---

## Git & GitHub Workflow Guide

This workflow applies to both the backend and frontend repositories. Use it for every Jira ticket so the branch, PR, and ticket stay connected.

### 1. Branching Strategy

- `main`: always deployable and reflects production
- `develop`: integration branch for completed work before release
- `<TICKET>-<description>`: one branch per Jira ticket where the actual work happens

Feature branches are created from `develop` and merged back into `develop`. `main` changes only through a reviewed release step.

### 2. Branch Naming Convention

Use the Jira ticket key exactly as shown in Jira, followed by a short kebab-case description:

```bash
git checkout -b AF-121-add-auth-token-refresh-endpoint
```

Examples:

- `AF-121-add-auth-token-refresh-endpoint`
- `AF-134-fix-student-lookup-pagination`
- `AF-140-add-request-validation-rule`

### 3. Commit Message Convention

Use a short, present-tense summary with the ticket key:

```bash
git commit -m "AF-121: add token refresh endpoint"
```

Examples:

- `AF-121: add token refresh endpoint`
- `AF-121: wire refresh logic to auth service`
- `AF-121: fix validation error for request payload`

### 4. Standard Workflow

1. Sync `develop` before starting work

```bash
git checkout develop
git pull origin develop
```

2. Create a branch for the ticket

```bash
git checkout -b AF-121-add-auth-token-refresh-endpoint
```

3. Work and commit in small checkpoints

```bash
git status
git add <file1> <file2>
git commit -m "AF-121: add token refresh endpoint"
```

4. Push early and often

```bash
git push -u origin AF-121-add-auth-token-refresh-endpoint
```

5. Keep the branch updated while you work

```bash
git fetch origin
git merge origin/develop
```

6. Check what will be included in the PR before pushing again

```bash
git status
git log --oneline origin/develop..HEAD
git log --oneline HEAD..origin/develop
git diff --stat origin/develop..HEAD
```

7. Open a pull request

- Base branch: `develop`
- Compare branch: your feature branch
- Title: `AF-121: add login form skeleton`
- Description: what changed, how to test it, and the Jira ticket link
- Include migration files and test evidence for backend changes

8. Respond to review feedback

```bash
git add <file>
git commit -m "AF-121: address review comment on refresh validation"
git push
```

9. Merge and clean up

Once approved, the project lead merges the PR using Squash and Merge. After that:

```bash
git checkout develop
git pull origin develop
git branch -d AF-121-add-auth-token-refresh-endpoint
```

### 5. Resolving Merge Conflicts

If `git merge origin/develop` reports conflicts:

```bash
git status
git diff --name-only --diff-filter=U
```

Open each conflicted file, keep the correct combined result, remove the conflict markers, then:

```bash
git add <resolved-file>
git status
git commit
git push
```

If needed, cancel the merge and try again:

```bash
git merge --abort
```

### 6. If the Branch Sat Untouched for a While

If the branch has been open for several days:

1. Commit or stash local work
2. Fetch the latest remote state
3. Compare with `develop`
4. Merge `origin/develop` and resolve conflicts
5. Re-run relevant backend checks before pushing

### 7. Quick Command Reference

- `git status`: see local changes and conflicts
- `git diff --name-only --diff-filter=U`: list conflicted files only
- `git log --oneline branchA..branchB`: compare commits between branches
- `git fetch origin`: download the latest remote state
- `git branch -vv`: see branch tracking status
- `git stash` / `git stash pop`: temporarily save or restore local changes
- `git merge --abort`: cancel an in-progress merge

### 9. Do's and Don'ts

Do:

- Sync from `develop` before starting a ticket and again if it stays open for more than a day or two
- Run `git status` before every add/commit
- Push early and often
- Keep PRs scoped to one ticket
- Include migration files and relevant tests for backend changes

Don't:

- Commit directly to `develop` or `main`
- Use `git add .` without checking `git status`
- Force-push to `develop` or `main`
- Leave a finished ticket unreviewed for too long

---

## CI/CD Pipeline

Automated pipeline stages run on every pull request and on merge to `main`:

- Install dependencies and run `ruff` / `black --check`
- Run `python manage.py makemigrations --check` to catch missing migrations
- Run the pytest suite with coverage
- Build the release artifact (versioned Python package / wheel)
- Deploy to staging automatically on merge to `develop`; deploy to production on a tagged release behind Gunicorn/Uvicorn with a reverse proxy such as Nginx and managed through the platform's process supervisor

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

1. Create a feature branch from `develop`
2. Implement the change following the standards in this guide
3. Run `ruff`, `black --check`, and `pytest` locally
4. Address review feedback and wait for approval

---


