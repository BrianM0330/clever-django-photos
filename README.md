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
bin/tailwindcss -i assets/css/input.css -o static/css/app.css --watch

# Terminal 2 — Django ASGI + WebSockets
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

For a one-shot production-style build (no watcher):

```bash
bin/tailwindcss -i assets/css/input.css -o static/css/app.css --minify
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
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Comma-separated hostnames. Set to your production domain. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Comma-separated origins, e.g. `https://gallery.example.com`. |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Any URL that `dj-database-url` understands (Postgres, MySQL, etc.). |
| `DJANGO_STATIC_ROOT` | `staticfiles/` | Where `collectstatic` writes. |
| `DJANGO_MEDIA_ROOT` | `media/` | Local filesystem for uploaded photos. |

When `DEBUG=False` the settings module flips on `SECURE_*` headers, HSTS, and
the manifest-static storage backend (cache-busting hashed filenames).

## [Deploy To VPS]

Target: a single small VPS such as a Hetzner CX22 or DigitalOcean basic droplet running
**Caddy → Daphne → Django ASGI** with **systemd** supervising the process.

This is intentionally not Fly.io / not Docker / not Kubernetes — it's the
simplest production setup that still does TLS, log rotation, and crash recovery
correctly. The migration doc has a full ladder for when you outgrow it.

Assumptions below:
- App user: `clever`
- App path: `/opt/clever/app`
- Domain: `gallery.example.com`
- Internal app port: `127.0.0.1:8000`

For Cloudflare DNS, create an `A` record for the subdomain pointing at the VPS IPv4 address, and an `AAAA` record only if the VPS has IPv6. Start with the record set to **DNS only** until Caddy successfully obtains a certificate. If you enable the Cloudflare proxy later, use SSL/TLS mode **Full (strict)**, not Flexible.

### One-time server setup

```bash
# On the VPS
sudo adduser --system --group --home /opt/clever clever
sudo apt install -y python3.13 python3.13-venv caddy git sqlite3 curl make
sudo -u clever git clone <repo> /opt/clever/app
cd /opt/clever/app
sudo -u clever python3.13 -m venv .venv
sudo -u clever .venv/bin/pip install --upgrade pip
sudo -u clever .venv/bin/pip install -r requirements.txt
sudo chmod o+x /opt/clever
```

The final `chmod` lets the `caddy` user traverse `/opt/clever` to read static/media files. The app directory and files remain owned by `clever`.

Install the Linux Tailwind standalone binary on the VPS. It is intentionally
gitignored because each platform needs a different binary:

```bash
cd /opt/clever/app
sudo -u clever mkdir -p bin
sudo -u clever curl -L -o bin/tailwindcss \
  https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.0/tailwindcss-linux-x64
sudo -u clever chmod +x bin/tailwindcss
```

Create `/opt/clever/app/.env`:

```bash
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<generate-a-long-random-secret>
DJANGO_ALLOWED_HOSTS=gallery.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://gallery.example.com
DATABASE_URL=sqlite:////opt/clever/app/db.sqlite3
DJANGO_STATIC_ROOT=/opt/clever/app/staticfiles
DJANGO_MEDIA_ROOT=/opt/clever/app/media
```

Generate a secret with:

```bash
python3.13 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

Bootstrap the database and static assets:

```bash
cd /opt/clever/app
sudo -u clever .venv/bin/python manage.py check
sudo -u clever .venv/bin/python manage.py migrate
sudo -u clever bash -lc 'set -a && . ./.env && set +a && make prod-build'
sudo -u clever .venv/bin/python manage.py seed_all
sudo -u clever sqlite3 db.sqlite3 'PRAGMA journal_mode=WAL;'
```

Manual production commands must load `.env`; `systemd` does this automatically through `EnvironmentFile`, but an SSH shell does not.

### Per-deploy

```bash
git pull
.venv/bin/pip install -r requirements.txt
bash -lc 'set -a && . ./.env && set +a && .venv/bin/python manage.py check && .venv/bin/python manage.py migrate && make prod-build'
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

The deployment examples live in `deploy/clever-daphne.service` and
`deploy/Caddyfile.example`.

### Verify

```bash
curl -I https://gallery.example.com/healthz/
curl -I https://gallery.example.com/
```

Check the hashed CSS URL rendered by the page:

```bash
python3 - <<'PY'
import re
import urllib.request

domain = "https://gallery.example.com"
html = urllib.request.urlopen(domain + "/").read().decode()
for path in re.findall(r'href="([^"]*css/[^"]+)"', html):
    url = domain + path if path.startswith("/") else path
    with urllib.request.urlopen(url) as response:
        print(response.status, response.headers.get("content-type"), url)
PY
```

### Troubleshooting

If root works but styles are missing, check the stylesheet directly. A `403` usually means Caddy cannot traverse `/opt/clever`; run `sudo chmod o+x /opt/clever`. A `404` usually means the Caddy `handle_path /static/*` mapping does not match `STATIC_ROOT` or `collectstatic` did not run.

If production raises `Missing staticfiles manifest entry`, rebuild static files with `.env` loaded:

```bash
cd /opt/clever/app
sudo -u clever bash -lc 'set -a && . ./.env && set +a && rm -rf staticfiles && make prod-build'
sudo systemctl restart clever-daphne
```

If `collectstatic` reports `css/tailwindcss` missing, make sure Tailwind source lives in `assets/css/input.css`, not under `static/`, and that only compiled `static/css/app.css` is collected.

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
content-source globs all live in `assets/css/input.css`. No `tailwind.config.js`,
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
