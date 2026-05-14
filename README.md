# Clever Gallery (Django)

Django 6.0 + HTMX + Alpine.js + Tailwind v4 photo gallery on SQLite.

A port of the Rails 8.1 + Hotwire reference under `TEMP_RAILS_REFERENCE/rails-hotwire-trial/`.
Same feature surface (auth, gallery, likes, comments, lightbox), different stack — chosen
to maximize what ships in stock Django and minimize third-party dependencies.

## Stack

- **Python 3.12+, Django 6.0** (uses the new native `django.tasks` framework)
- **SQLite** by default; **Postgres** opt-in via `DATABASE_URL=postgres://…` (`dj-database-url`)
- **HTMX 2.0** as the Turbo Streams analog (server-rendered HTML partials)
- **Alpine.js 3** for small client-side interactivity (optimistic UI, toggles)
- **Tailwind CSS v4** via the standalone CLI binary (no Node, no `tailwind.config.js`)
- **PhotoSwipe 5** lightbox (CDN)
- **Whitenoise** for static asset serving in production
- **Daphne + Channels** for ASGI HTTP/WebSocket serving
- **`django.contrib.auth`** stock — email login via a custom `User(AbstractUser)`,
  no Devise/Allauth equivalent, no password reset flow, no social login
- **`django.tasks`** with the in-process `immediate` backend; swap to
  `django-tasks-db` for a real worker without changing call sites
- **Built-in `unittest`** runner via `manage.py test` — no pytest

See `docs/RAILS_MIGRATION.md` for the full porting plan, phase-by-phase status,
and a "Scaling Up When Needed" section that walks each subsystem
(jobs, DB, cache, media, observability, deploy) from the take-home defaults to
real production.

## Local development

### One-time setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # includes runtime deps + honcho
python manage.py migrate
```

Production servers install `requirements.txt` only — `requirements-dev.txt` adds
`honcho` (the process manager that powers `bin/dev`) and any other dev-only tools.

Tailwind ships as a single static binary at `bin/tailwindcss` (gitignored).
If it's missing, download the macOS arm64 build from the
[Tailwind v4 releases page](https://github.com/tailwindlabs/tailwindcss/releases)
and drop it in:

```bash
curl -L -o bin/tailwindcss \
  https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.0/tailwindcss-macos-arm64
chmod +x bin/tailwindcss
```

### Run the dev server

One command runs both Django and the Tailwind watcher:

```bash
bin/dev
```

This wraps `honcho -f Procfile.dev start`, which starts the two processes
declared in `Procfile.dev` (`web: daphne ... config.asgi:application` and
`css: bin/tailwindcss … --watch`), interleaves their logs, and shuts both
down on `Ctrl-C`. Visit <http://127.0.0.1:8000/>.

If you'd rather run them separately (clearer Tailwind error output):

```bash
# Terminal 1 — Tailwind watcher
bin/tailwindcss -i static/css/input.css -o static/css/app.css --watch

# Terminal 2 — Django ASGI + WebSockets
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

For a one-shot production-style build (no watcher):

```bash
bin/tailwindcss -i static/css/input.css -o static/css/app.css --minify
```

### Tests

```bash
python manage.py test           # full suite
python manage.py test apps.core # one app
python manage.py test apps.core.tests.LandingViewTests.test_landing_renders_with_frontend_toolchain
python manage.py check          # config sanity check
```

## DB seeding

A single management command mirrors the Rails `db/seeds.rb`:

```bash
python manage.py seed_all
```

It is **idempotent** — safe to re-run. It loads:

- 5 users (`brian`, `ryan`, `jake`, `mike`, `admin`) — all `<name>@clever.com`,
  password `password`
- 10 photos from `data/seeds/photos.csv` (the same CSV used by the Rails app)
- Deterministic likes/comments seeded modulo user/photo IDs so demo state is
  predictable across reruns

Reset and reseed from scratch:

```bash
rm db.sqlite3
python manage.py migrate
python manage.py seed_all
```

> **Status:** the `seed_all` command lands in Phase 5 of `docs/RAILS_MIGRATION.md`.
> Until then, create a superuser manually with `python manage.py createsuperuser`.

## Configuration

All config is environment-driven (read in `config/settings.py`), with sensible
defaults so the app boots with zero env vars:

| Var | Default | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | dev-only insecure default | **Required in production.** |
| `DJANGO_DEBUG` | `True` | Set to `False` in production. |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated list. |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Any URL that `dj-database-url` understands (Postgres, MySQL, etc.). |
| `DJANGO_STATIC_ROOT` | `staticfiles/` | Where `collectstatic` writes. |
| `DJANGO_MEDIA_ROOT` | `media/` | Local filesystem for uploaded photos. |

When `DEBUG=False` the settings module flips on `SECURE_*` headers, HSTS, and
the manifest-static storage backend (cache-busting hashed filenames).

## Deployment

Target: a single small VPS (Hetzner CX22 or DigitalOcean $6 droplet) running
**Caddy → Daphne → Django ASGI** with **systemd** supervising the process.

This is intentionally not Fly.io / not Docker / not Kubernetes — it's the
simplest production setup that still does TLS, log rotation, and crash recovery
correctly. The migration doc has a full ladder for when you outgrow it.

### One-time server setup

```bash
# On the VPS
adduser --system --group --home /opt/clever clever
apt install -y python3.12 python3.12-venv caddy
sudo -u clever git clone <repo> /opt/clever/app
cd /opt/clever/app
sudo -u clever python3.12 -m venv .venv
sudo -u clever .venv/bin/pip install -r requirements.txt
```

### Per-deploy

```bash
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
bin/tailwindcss -i static/css/input.css -o static/css/app.css --minify
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart clever-daphne
```

### Systemd unit (`/etc/systemd/system/clever-daphne.service`)

```ini
[Unit]
Description=Clever Gallery (Daphne)
After=network.target

[Service]
User=clever
Group=clever
WorkingDirectory=/opt/clever/app
EnvironmentFile=/opt/clever/app/.env
ExecStart=/opt/clever/app/.venv/bin/daphne \
  -b 127.0.0.1 -p 8000 config.asgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Caddyfile

```caddy
gallery.example.com {
    encode zstd gzip
    handle_path /static/* {
        root * /opt/clever/app/staticfiles
        file_server
    }
    handle_path /media/* {
        root * /opt/clever/app/media
        file_server
    }
    reverse_proxy 127.0.0.1:8000
}
```

Caddy handles TLS automatically via Let's Encrypt. Backups: a nightly cron
`sqlite3 db.sqlite3 ".backup /backups/db-$(date +%F).sqlite3"` is enough for
this scope; consider [Litestream](https://litestream.io/) → S3/B2 for
point-in-time recovery once it matters.

## Architectural decisions

### Why Django 6.0 (not 5.2 LTS)

6.0 ships **`django.tasks`** in the stdlib — a generic background-task API with
swappable backends. The take-home runs the `immediate` (in-process) backend so
there's nothing to install. Promoting to a real worker is a one-line setting
change to `django-tasks-db` (SQLite/Postgres-backed queue) — no Celery, no
Redis, no broker. See the "Scaling Up" section of `docs/RAILS_MIGRATION.md`.

### Auth

Stock `django.contrib.auth` with a custom `User(AbstractUser)` for email login.
No Allauth, no JWT, no `django-axes` — all overkill for the scope. Sign-up is
enabled to make the demo interactive (matches the Rails reference).

### Frontend

HTMX + Alpine instead of a SPA. Server renders HTML partials; HTMX swaps
fragments; Alpine handles the small interactive bits (like-button optimistic
flip, toast dismissal). No build step beyond Tailwind. Both libraries are
loaded from CDN at pinned versions for reproducibility — easy to vendor into
`static/` later (the migration doc covers this when CSP gets tightened).

Realtime like counts use Django Channels over WebSockets. The initial deployment
uses Channels' in-memory layer, which is deliberately single-process: one Daphne
process owns the connected sockets and broadcasts. If you run multiple ASGI
workers or multiple app servers, add `channels-redis` and configure `REDIS_URL`
so broadcasts reach sockets connected to other processes.

### Tailwind

Tailwind v4's CSS-only configuration: theme tokens, components, and
content-source globs all live in `static/css/input.css`. No `tailwind.config.js`,
no PostCSS, no Node. The standalone binary is the only build dependency.

### Likes and comments

`Like` enforces uniqueness with a `UniqueConstraint("user", "photo")`; the view
uses `Like.objects.get_or_create(...)` for idempotent toggles — same pattern as
the Rails `create_or_find_by`.

### Counter caches

`Photo.likes_count` / `Photo.comments_count` updated by `post_save` /
`post_delete` signals using `F()` expressions to avoid race conditions on
concurrent updates. Avoids N+1 on the gallery index without an aggregation
query.

When likes change, the HTTP view broadcasts the fresh aggregate `likes_count` to
authenticated WebSocket clients watching that photo. The current user's personal
`liked` state still comes from the HTMX response; realtime only updates the
global count.

### Tests

`django.test.TestCase` + `manage.py test`. The built-in runner is fast enough
for this scope and removes a dependency. No pytest, no factory-boy — fixtures
are built in setUp with the seed users.

## Project layout

```
.
├── apps/                     # All first-party apps live under this namespace
│   ├── accounts/             # Auth views/forms/templates (Phase 4 — stock `auth.User`)
│   ├── core/                 # Landing, healthz, base templates
│   ├── photos/               # Photo, Like, Comment models + views (Phase 3+)
│   └── …
├── config/                   # Django project module
│   ├── settings.py           # env-driven, single file
│   ├── urls.py
│   └── wsgi.py
├── bin/tailwindcss           # Tailwind v4 standalone binary (gitignored)
├── data/seeds/photos.csv     # Source data for `seed_all`
├── docs/RAILS_MIGRATION.md   # Master plan + phase status + scaling guide
├── static/                   # CSS source, JS, images
├── templates/                # Project-level templates (base.html, etc.)
├── TEMP_RAILS_REFERENCE/     # The Rails reference app — delete after parity
├── manage.py
└── requirements.txt
```

## AI-assisted sections

In a short build window I let an AI pair (this repo was built with `opencode`)
handle scaffolding so I could focus on architecture and parity:

- Initial Django project scaffold and settings layout
- Tailwind v4 `@theme` palette translation from the Rails source
- Base template structure (skip link, navbar shell, messages, footer)
- README and migration-doc prose

Backend correctness — model design, constraint choices, signal-driven counter
caches, the `django.tasks` decision, the SQLite-to-Postgres migration recipe —
is mine.
