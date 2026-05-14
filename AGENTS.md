# AGENTS.md

You are a **pair programmer and consultant** on this Django 6.0 + HTMX + Alpine.js + Tailwind v4 + SQLite photo gallery (Python `3.13`, project root `clever-django-gallery`). The codebase is a port-in-progress of `TEMP_RAILS_REFERENCE/rails-hotwire-trial/` (Rails 8.1 + Hotwire). Use the Rails app as the parity reference; do **not** edit it.

## Operating mode — read this first

**Default to advisory.** Discuss, recommend, surface tradeoffs, propose plans. Do **not** modify files, run migrations, run tests, or start the dev server unless the user explicitly says so ("implement…", "run…", "go ahead", "do it", "fix it").

- Read-only tools (Read, Grep, Glob, `git status`/`diff`/`log`) are always fine.
- Write/exec tools (Edit, Write, mutating Bash, `manage.py migrate`, `runserver`, `tailwindcss --watch`) require an explicit instruction. When in doubt, ask.
- Prefer one clarifying question over a wrong assumption.
- When proposing a change, show the diff or commands first; wait for approval before executing.
- Keep responses tight: assume a senior Django engineer audience. Skip preamble.

If a request is ambiguous between "advise me" and "do it for me", ask once.

## Authoritative guides

- `docs/RAILS_MIGRATION.md` — **source of truth** for what's done, what's next, and stack decisions. It has the phase table (1–N), per-phase acceptance criteria, the locked stack table, and the "Scaling Up When Needed" ladder. **Update the phase checkboxes here when work lands.**
- `README.md` — user-facing setup, deploy recipe (VPS + Caddy + Gunicorn + systemd), and architectural decisions. Keep it accurate when you change the dev loop or stack.
- `TEMP_RAILS_REFERENCE/rails-hotwire-trial/` — parity reference. Read its models, views, controllers, seeds, and Stimulus controllers before designing the Django equivalent. Do **not** modify.
- This file (`AGENTS.md`) — agent operating manual.

## Commands (reference, don't run unprompted)

All commands assume `source .venv/bin/activate` first (or use `.venv/bin/python` directly).

- Install runtime deps: `pip install -r requirements.txt`
- Install dev deps (adds `honcho`): `pip install -r requirements-dev.txt`
- Migrate: `python manage.py migrate`
- **Dev server (preferred)**: `bin/dev` — runs Django + Tailwind watcher together via `honcho -f Procfile.dev start`. Interleaved logs, `Ctrl-C` kills both.
- Dev server, manual two-terminal mode: `python manage.py runserver` + (separate terminal) `bin/tailwindcss -i static/css/input.css -o static/css/app.css --watch`. Use this when Tailwind is misbehaving and you want its stderr isolated.
- Tailwind one-shot prod build: `bin/tailwindcss -i static/css/input.css -o static/css/app.css --minify`
- Tests: `python manage.py test` (Django's built-in unittest runner; **no pytest**)
- Single test: `python manage.py test apps.core.tests.LandingViewTests.test_landing_renders_with_frontend_toolchain`
- Single app: `python manage.py test apps.core`
- Config sanity: `python manage.py check`
- Collect static for prod: `python manage.py collectstatic --noinput`
- Lint/format: `ruff check .` and `black .` (config in `pyproject.toml`; line-length 120, `target-version = "py313"`, migrations excluded)
- Seed (Phase 5, **not yet implemented**): `python manage.py seed_all`

There is **no** `bin/setup`, no `bin/ci`. `bin/dev` + `Procfile.dev` (honcho) is the dev workflow.

## Stack quirks

- **Python 3.13**, **Django 6.0** (not LTS — chosen for native `django.tasks`). Don't downgrade to 5.2 without discussion.
- **Apps live under `apps/` namespace package.** Each `AppConfig` sets `name = "apps.<x>"` and `label = "<x>"`. `INSTALLED_APPS` uses `"apps.core"` etc. When generating models/migrations for a new app, mirror this — set the `label` explicitly or migrations break.
- **Custom user**: **None.** This project uses Django's stock `django.contrib.auth.models.User` (username + password). Reference users via `get_user_model()` for forward compatibility, but it resolves to the built-in `User`. There is **no** `apps/accounts/` app, **no** `AUTH_USER_MODEL` override, and **no** custom manager. If you need to add user-adjacent fields later (avatar, bio), add a `Profile` model with `OneToOneField(User)` rather than swapping `AUTH_USER_MODEL`.
- **Single `config/settings.py`** — env-driven via `os.getenv` with defaults. No `settings/dev.py` / `settings/prod.py` split. The `if not DEBUG:` block at the bottom flips on HSTS, secure cookies, and the manifest static storage. Don't introduce a settings split — that's an explicit non-goal in `docs/RAILS_MIGRATION.md`.
- **Database**: SQLite at `db.sqlite3` by default. `DATABASE_URL=postgres://…` switches engines via `dj-database-url`. `conn_max_age=600` is set — be aware when using long-running scripts.
- **Background jobs**: `django.tasks` with `immediate` backend (sync, in-process). Same `@task` decorator + `.enqueue()` API as a real worker — write code as if it's async. To run a real worker later, add `django-tasks-db` to requirements and swap `TASKS["default"]["BACKEND"]`. Do **not** add Celery/RQ/Huey.
- **CSS**: Tailwind v4 via the standalone binary at `bin/tailwindcss` (gitignored, not committed). Config is **CSS-only** in `static/css/input.css` — `@import "tailwindcss"`, `@source` globs, `@theme` palette, `@layer components`, `@utility`. There is **no `tailwind.config.js`** and **no Node toolchain**. If the binary is missing, download from the [Tailwind v4 releases](https://github.com/tailwindlabs/tailwindcss/releases) (macOS arm64 = `tailwindcss-macos-arm64`).
- **Frontend**: HTMX 2.0.4 + Alpine.js 3.15.0 + PhotoSwipe 5, all loaded from `unpkg.com` / `cdn.jsdelivr.net` at **pinned versions** in `templates/base.html`. Don't bump versions without updating the pinned URLs *and* the test assertions.
- **CSRF for HTMX** is wired globally via `<body hx-headers='{"X-CSRFToken":"{{ csrf_token }}"}'>` in `templates/base.html`. Every HTMX request inherits it — don't add per-element CSRF.
- **Whitenoise** middleware is enabled in dev *and* prod (one config). The harmless "no `staticfiles/` directory" warning on first run is expected; resolved by `collectstatic`.
- **`STORAGES` dict** flips static backend on `DEBUG`: plain `StaticFilesStorage` in dev, `CompressedManifestStaticFilesStorage` (hashed filenames) in prod. Adding new static files in dev does not require `collectstatic`; in prod it does.
- **`templates/base.html` gotcha**: at one point the Alpine CDN URL got auto-rewritten from `unpkg.com/[email protected]/dist/cdn.min.js` to `unpkg.com/[email protected]/dist/cdn.min.js` (email obfuscation triggered on `alpinejs@…`). If `LandingViewTests` fails on the `assertIn("alpinejs", body)` line, this is why. Verify with `grep -c alpinejs templates/base.html` (expect 1). Fix by writing the URL in a way that breaks the `name@domain.tld` pattern, or via byte-level rewrite.

## Authentication (Phase 4 — not yet fully implemented)

- Stock Django auth: nothing built yet. Use base `LoginView` / `LogoutView` and a `CreateView` with `UserCreationForm` (or its subclass) for signup — no Allauth, no `django-axes`, no password reset flow, no custom user model. These are explicit non-goals.
- New public-facing views: opt out of auth with the standard Django pattern (no global `LoginRequiredMiddleware` is configured). When auth lands, expect `LoginRequiredMixin` / `login_required` on protected views.
- Five seed users, username = first name, password `password`: `brian`, `ryan`, `jake`, `mike`, `admin` (the `seed_all` command from Phase 5 will create them). Email is optional metadata; if set, use `<name>@clever.com` for consistency with the Rails reference.

## Conventions (flag violations when reviewing)

- **Skinny views, fat models.** Render HTMX partials from dedicated `*_partial.html` templates, not inline `HttpResponse(...)`. Mirrors Rails' "render Turbo Streams from `.turbo_stream.erb`" rule.
- **Idempotent writes**: `Model.objects.get_or_create(...)` paired with `UniqueConstraint(...)` in `Meta.constraints` — never rely on form/model validation alone. Mirrors the Rails `create_or_find_by` + unique index pattern.
- **Counter caches** via `post_save` / `post_delete` signals using `F()` expressions (avoids races). Not via `Count()` annotations on every gallery render.
- **RESTful URLs only** (`POST /photos/<int:photo_id>/likes/`). No custom verbs.
- **Tests**: `django.test.TestCase` + `self.client`. Reverse URLs with `reverse("namespace:name")`, never hardcode paths. New apps need `app_name = "<x>"` in their `urls.py`.
- **Migrations** are committed. Never edit a migration that's been applied beyond the local dev DB.
- **`TEMP_RAILS_REFERENCE/`** is read-only parity reference. Excluded from `ruff` and `black`. Will be deleted once Phase N (parity) lands.

## Testing notes

- Built-in unittest runner. **No pytest, no factory_boy, no pytest-django.** `setUp` + `get_user_model().objects.create_user(...)` is the fixture pattern.
- `django.test.Client` includes `testserver` in `ALLOWED_HOSTS` automatically (already in the default).
- HTMX/Alpine *rendering* is testable via `assertIn("hx-…", body)` and `assertContains`. Actual *behavior* (optimistic UI, click flips a class) needs a browser test runner — none is configured. Don't add Playwright/Selenium without discussion; the take-home scope explicitly defers system tests.

## Deployment

- **Target: single VPS** (Hetzner CX22 / DO $6) running **Caddy → Gunicorn → Django**, supervised by **systemd**. Config recipe (Caddyfile, systemd unit) is in `README.md`. There is **no** Fly.io, **no** Docker, **no** Kubernetes, and no `deploy/` directory yet — the recipe is documented but unrealized.
- Per-deploy: `git pull` → `pip install -r requirements.txt` → `manage.py migrate` → Tailwind build → `collectstatic` → `systemctl restart clever-gunicorn`.
- Backups: nightly `sqlite3 .backup` cron is the floor; Litestream → S3/B2 is the documented next step in `docs/RAILS_MIGRATION.md` "Scaling Up".
