# Rails → Django Migration Guide & Progress Tracker

Living document. Update statuses as work lands.

This is a take-home interview project: porting the Rails 8.1 + Hotwire photo gallery (`TEMP_RAILS_REFERENCE/rails-hotwire-trial/`) to Django + Alpine.js + HTMX. **Goal: simple, senior-grade, production-ready Django — no bloat.**

Companion to `TEMP_RAILS_REFERENCE/rails-hotwire-trial/docs/DOCS_GALLERY_PROGRESS.md` — same legend, different stack.

## Legend

- `[ ]` **TODO** — not started
- `[~]` **WIP** — in progress
- `[x]` **DONE** — landed
- `[!]` **BLOCKED** — see notes
- `[-]` **SKIPPED** — explicitly out of scope

---

## Locked Stack Decisions (Phase 0)

| Concern | Choice | Notes |
|---|---|---|
| Runtime | Python 3.13 | Mirrors Ruby 3.4 cadence |
| Framework | Django 6.0 | Latest stable; ships native `django.tasks` |
| Database | **SQLite by default; Postgres via `DATABASE_URL`** | `dj-database-url` switches engines from one env var. Local Postgres is `brew install postgresql` + `createdb` if you want it |
| ORM | Django ORM | No SQLAlchemy |
| Auth | `django.contrib.auth` + custom `User(AbstractUser)` with email login | Built-in `LoginView`/`LogoutView`/`UserCreationForm`. **No** custom session model |
| Templates | Django Templates (DTL) | Native, no Jinja2 |
| CSS | Tailwind CSS v4 standalone CLI | CSS-only config (`@theme`, `@source`, `@utility`) — no Node, no `tailwind.config.js` |
| JS framework | **Alpine 3** + **HTMX 2** | HTMX = Turbo Streams analog. Alpine = optimistic local state |
| JS bundling | None — CDN scripts + tiny hand-written `app.js` | |
| Object storage | Local filesystem (`MEDIA_ROOT`) | |
| Image processing | Pillow when uploads land | |
| Background tasks | **Django 6.0 native `django.tasks`** with `immediate` backend (synchronous, in-process). Real worker = install `django-tasks-db` later | Same `@task` + `.enqueue()` API as a real distributed worker. No Redis, no SQS, no Docker |
| Static files | Whitenoise (compressed manifest) in prod | |
| WSGI | Gunicorn (sync workers) | |
| Reverse proxy | Caddy | Auto-HTTPS |
| Config | `os.getenv` with sane defaults — single `settings.py`, `if not DEBUG:` block for prod hardening | No `django-environ`, no settings split |
| Env file (optional) | None required. `os.getenv` with defaults works out of the box. Add a `.env` + `python-dotenv` only if you actually need it | |
| Testing | `python manage.py test` — Django's built-in `TestCase` + `Client` | Auto-creates SQLite test DB. No pytest, no factory_boy unless real need emerges |
| Linting | Ruff + Black (minimal config in `pyproject.toml`) | No mypy strict, no djlint until pain demands them |
| Hosting | VPS (Hetzner CX22 ~$4/mo or DO $6/mo) + Caddy + gunicorn + systemd | |

**Guiding philosophy:** *Use as much base Django as possible.* Skinny views, fat models, idempotent writes backed by DB constraints. No premature abstractions. Every file in this repo earns its place.

---

## Status Snapshot

| Phase | Area | Status | Notes |
|-------|------|--------|-------|
| 0 | Stack lock-in & principles | `[x]` | |
| 1 | Django scaffolding (single settings.py, three apps, healthz) | `[x]` | Boots, healthz returns 200, `manage.py test` green |
| 2 | Frontend toolchain (Tailwind v4, Alpine, HTMX, base layout) | `[x]` | Tailwind v4.3 binary in `bin/`, base layout + landing smoke page render with Alpine + HTMX live |
| 3 | Models (User, Photo, Like, Comment) + first real tests | `[x]` | Models, migration, and tests landed; `manage.py test` green |
| 4 | Auth (`django.contrib.auth` only) | `[ ]` | No password reset, no axes, no custom session model |
| 5 | `seed_all` management command | `[ ]` | |
| 6 | Views & URL routing | `[ ]` | |
| 7 | Templates (Tailwind v4 CSS-only) | `[~]` | Landing page + shared navbar ported from Rails; gallery/auth templates pending |
| 8a | Like button (HTMX + Alpine optimistic) | `[ ]` | |
| 8b | Copy-source button (pure Alpine) | `[ ]` | |
| 8c | Lightbox (PhotoSwipe) | `[ ]` | |
| 8d | Comments (HTMX append + Alpine UX) | `[ ]` | |
| 9 | Counter caches via signals + `F()` expressions | `[ ]` | |
| 10 | Async pipeline via `django.tasks` (when uploads land) | `[ ]` | Demo task wired immediately; real upload pipeline deferred |
| 11 | Test coverage pass | `[ ]` | Just `manage.py test`; add system tests if time permits |
| 12 | VPS deployment | `[ ]` | |

---

## Phase 1 — Django Scaffolding [DONE]

**Goal:** A booting Django app with sensible defaults, three empty app shells, and a healthcheck.

**Final layout:**
```
clever-django-gallery/
├── manage.py
├── pyproject.toml          # ruff + black, minimal
├── requirements.txt        # flat
├── .gitignore
├── config/
│   ├── __init__.py
│   ├── settings.py         # SINGLE FILE; if not DEBUG: prod hardening
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── __init__.py
│   ├── core/               # healthz, base templates (later)
│   └── photos/             # Photo, Like, Comment (Phase 3)
├── templates/              # (Phase 2/7)
└── static/                 # (Phase 2)
    ├── css/
    ├── js/
    └── images/
```

**Configuration choices:**
- `SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-…")` — works without `.env`; override in prod via real env var
- `DATABASES["default"] = dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")` — SQLite default, `DATABASE_URL=postgres://…` switches to Postgres
- `AUTH_USER_MODEL` is **not** overridden — uses Django's stock `auth.User` (username + password). Decision deliberate: keeps the auth surface minimal for a take-home.
- `apps.core/photos` — apps live under `apps/` namespace; `apps.py` files use `name = "apps.<x>"` + `label = "<x>"`
- `TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}` — Django 6.0 native; runs sync in-process; swap backend when real worker is needed

**Acceptance:**
- ✅ `manage.py check` clean
- ✅ `manage.py migrate` succeeds (SQLite, default path)
- ✅ `manage.py runserver` boots; `GET /healthz/` returns `200 {"status":"ok"}`
- ✅ `manage.py test` finds and runs `apps/core/tests.py::HealthzViewTests` green

**What we explicitly did NOT do** (and why):
- No split settings (dev/test/prod). Single `settings.py` with `if not DEBUG:` block is enough for a take-home.
- No `django-environ`. `os.getenv` with defaults is one less dependency.
- No `bin/setup`, `bin/dev`, `bin/ci`, `Procfile.dev`, `honcho`. `manage.py runserver` is the dev command. CI is one `pytest`-or-`manage.py test` line in a GitHub Actions YAML.
- No `requirements/{base,dev,prod}.txt` split. One `requirements.txt`. Add `requirements-dev.txt` only if dev tooling proliferates.
- No `pytest`, no `factory_boy`, no `django-stubs`. `manage.py test` + `TestCase` covers the take-home scope cleanly.
- No `django-axes`. Login throttling is over-engineering for a take-home; default Django auth is fine.
- No `mypy --strict`. Type hints in new code; no enforcement.
- No `djlint`. Templates are reviewed by eye.

---

## Phase 2 — Frontend Toolchain (Tailwind v4 + Alpine + HTMX)

**Goal:** Tailwind v4 compiles via standalone CLI (CSS-only config), Alpine + HTMX load via CDN, base layout renders.

- [x] Download `tailwindcss` standalone binary into `bin/tailwindcss`; gitignore it
- [x] `static/css/input.css` with `@import "tailwindcss"`, `@theme` block (port `clever-*` palette + `fade-in-down` keyframes from Rails), `@source` lines pointing at `templates/` and `apps/**/templates/`, `@utility` for `mask-glow-sweep`
- [x] Run command (Phase 2 add to README): `bin/tailwindcss -i static/css/input.css -o static/css/app.css --watch`
- [x] `templates/base.html`: title block, CSRF meta, skip link, navbar/flash partials, content block, footer
- [x] `templates/base.html` head loads Alpine + HTMX from CDN; sets `<body hx-headers='{"X-CSRFToken":"{{ csrf_token }}"}'>` so HTMX requests carry CSRF
- [x] `static/js/app.js`: any shared Alpine helpers (e.g., toast registration); served via Django staticfiles in dev, Whitenoise in prod
- [x] Add `STATIC_URL`, `STATICFILES_DIRS`, `STATIC_ROOT` (already in settings); add Whitenoise middleware + `STORAGES` config

**Acceptance:** Landing route renders base layout with Tailwind classes; `console.log(window.htmx, window.Alpine)` shows both loaded. ✅ `LandingViewTests.test_landing_renders_with_frontend_toolchain` passes.

---

## Phase 3 — Models

**Goal:** Four models matching the Rails schema. No elaborate parity test suite — just normal model tests proving constraints work.

**Mapping:**

| Rails table | Django model | Notes |
|---|---|---|
| `users` | `django.contrib.auth.models.User` (stock) | Username-based login. No custom user model — see Phase 4 rationale. Email is optional metadata. |
| `photos` | `photos.Photo` | All Rails fields; `pexels_id` unique; `likes_count` / `comments_count` `PositiveIntegerField(default=0)`; port the 8 `src_*` URL methods + `srcset()` from Rails `Photo` model |
| `likes` | `photos.Like` | FKs cascade; `Meta.constraints = [UniqueConstraint("user","photo", name="uniq_user_photo_like")]` |
| `comments` | `photos.Comment` | `body` TextField + `MaxLengthValidator(1000)`; `Meta.indexes = [Index(fields=["photo","created_at"])]` |

**Implementation:**

- [x] Use stock `django.contrib.auth.models.User` (no custom user model). Decision: no `AUTH_USER_MODEL` override, no custom manager — keeps auth surface minimal. If profile fields are needed later, add a `Profile` model with `OneToOneField(User)`.
- [x] `photos.Photo` with all 14 columns
- [x] `photos.Photo.src_*` methods + `srcset()` ported verbatim
- [x] `photos.Like` with unique constraint
- [x] `photos.Comment` with body validator + composite index
- [x] `manage.py makemigrations photos && migrate`

**Tests (`apps/photos/tests.py`):**

- [x] `test_unique_user_photo_like_constraint_enforced` — second `Like.objects.create(user, photo)` raises `IntegrityError`
- [x] `test_photo_pexels_id_unique_constraint_enforced`
- [x] `test_comment_body_max_length_1000` — `full_clean()` raises `ValidationError`
- [x] `test_photo_src_large_matches_pexels_pattern` — generated URL matches the format from `photos.csv`

**Acceptance:** ✅ `manage.py test` green; constraint violations actually raise `IntegrityError` not silent failures.

---

## Phase 4 — Auth (Base Django)

**Goal:** Username/password login, signup, logout. No password reset, no axes, no custom user model.

- [ ] `apps/accounts/forms.py`: subclass `UserCreationForm` if any tweaks needed (otherwise use stock)
- [ ] `apps/accounts/views.py`: thin wrappers around `LoginView`, `LogoutView`, `SignupView(CreateView)` that auto-logs-in on success
- [ ] `apps/accounts/urls.py`: `login/`, `logout/`, `signup/` (create the app fresh — views/forms/urls/templates only, no models)
- [ ] `templates/accounts/{login,signup}.html` (Tailwind-styled)
- [ ] `LOGIN_URL = "/login/"`, `LOGIN_REDIRECT_URL = "/photos/"`, `LOGOUT_REDIRECT_URL = "/"`
- [ ] Use `@login_required` on gallery views (no global middleware needed for this scope)

**Tests:**
- [ ] Signup with new username → user exists, logged in, redirected to `/photos/`
- [ ] Login with wrong password → form re-renders with error
- [ ] Logout → redirect to root, session cleared
- [ ] `/photos/` while logged out → redirects to `/login/?next=/photos/`

---

## Phase 5 — `seed_all` Management Command

**Goal:** `manage.py seed_all` reproduces `db/seeds.rb` exactly. Idempotent.

- [ ] Copy `TEMP_RAILS_REFERENCE/rails-hotwire-trial/photos.csv` → `data/seeds/photos.csv`
- [ ] `apps/photos/management/commands/seed_all.py`:
  - `_seed_photos()`: `Photo.objects.update_or_create(pexels_id=int(row["id"]), defaults={...})`
  - `_seed_users()`: 5 users (`brian, ryan, jake, mike, admin`) via `User.objects.update_or_create(username=..., defaults={"email": f"{name}@clever.com"})` + `set_password("password")`
  - `_seed_social()`: ports the modulo math from Rails seeds for deterministic likes/comments
  - All wrapped in `transaction.atomic()`
  - Print summary counts

**Tests:**
- [ ] `test_seed_all_creates_expected_counts` — call command, assert 10 photos, 5 users, expected like/comment counts
- [ ] `test_seed_all_is_idempotent` — call twice, counts unchanged

---

## Phase 6 — Views & URL Routing

| Rails route | Django URL | View | Auth |
|---|---|---|---|
| `root "landing#index"` | `""` | `core.views.LandingView` (TemplateView) | public |
| `resources :photos, only: [:index, :show]` | `photos/`, `photos/<int:pk>/` | `photos.views.PhotoListView`, `PhotoDetailView` | `@login_required` |
| `resource :like` | `photos/<int:pk>/like/` POST/DELETE | `photos.views.LikeToggleView` | `@login_required` |
| `resources :comments` (8d) | `photos/<int:pk>/comments/` POST, `comments/<int:pk>/` DELETE | `CommentCreateView`, `CommentDestroyView` | `@login_required` |
| `/up` healthcheck | `/healthz/` | `core.views.healthz` | public |

- [ ] `LikeToggleView`: POST = `Like.objects.get_or_create(user, photo)`; DELETE = `.filter(...).delete()`; refresh photo from DB; if `HX-Request` header → render `_like_button.html` partial, else JSON

**Tests:** every URL hit via `Client`, status + template assertions; `POST /photos/1/like/` twice → 1 row, `likes_count == 1`.

---

## Phase 7 — Templates (Tailwind v4 CSS-Only)

```
templates/
├── base.html
├── partials/{navbar,flash,footer}.html
├── core/landing.html
├── photos/{photo_list,photo_detail,_photo_card,_like_button,_like_count,_comment}.html
└── accounts/{login,signup}.html
```

Port `app/views/` from the Rails reference 1:1, swapping ERB for DTL. Custom template tags in `apps/core/templatetags/photo_tags.py`: `inline_svg`, `dom_id`, `pluralize_count`.

**Landed early (out of phase order, for debugging/visual feedback):**
- [x] `apps/core/templates/core/landing.html` — full port of Rails `landing/index.html.erb` including hero CTAs, auth-aware copy, and the animated SVG architecture illustration. Auth-gated links stubbed with `#` + `TODO(phase-4/5)` comments until login/signup/photos routes land.
- [x] Navbar ported into `templates/base.html` directly (replacing the Phase 2 placeholder header). Will move to `templates/partials/navbar.html` when other pages need to override it. Logout uses an inline CSRF-protected `<form method="post">` instead of a link, per Django conventions.
- [x] `static/css/input.css` — added `animate-draw` + `delay-{150,300,450,600}` `@utility` rules (and `draw` keyframes) ported from Rails `app/assets/tailwind/application.css` so the hero illustration's line-draw animation works.
- [x] `apps/core/tests.py` — landing now has 5 tests covering anonymous vs. authenticated CTAs, navbar variants, and presence of the hero illustration's animation hooks.

**Acceptance:** Side-by-side visual diff vs. Rails — zero perceptible delta.

---

## Phase 8a — Like Button (HTMX + Alpine Optimistic)

```html
<div id="{% dom_id photo 'like' %}"
     x-data="{ liked: {{ liked|yesno:'true,false' }}, count: {{ photo.likes_count }} }"
     hx-post="{% url 'photos:like_toggle' photo.pk %}"
     hx-trigger="click from:button"
     hx-swap="outerHTML">
  <button @click="liked = !liked; count += liked ? 1 : -1" :aria-pressed="liked">
    {% inline_svg "star-fill.svg" x-show="liked" %}
    {% inline_svg "star-line.svg" x-show="!liked" %}
    <span x-text="count" class="tabular-nums"></span>
  </button>
</div>
```

- [ ] Server returns the rendered partial with the new state
- [ ] CSRF via `<body hx-headers='{"X-CSRFToken":"{{ csrf_token }}"}'>`
- [ ] No-JS fallback: form submission still works

---

## Phase 8b — Copy-Source Button (Pure Alpine)

Port of `app/javascript/controllers/copy_source_controller.js`:

```html
<div x-data="{ copied: false }" class="relative">
  <button @click="navigator.clipboard.writeText('{{ photo.url }}'); copied = true; setTimeout(() => copied = false, 2000)">
    {% inline_svg "copy.svg" %}
  </button>
  <span x-show="copied" x-transition class="absolute -top-8 …">Copied</span>
</div>
```

No server endpoint. Pure client-side.

---

## Phase 8c — Lightbox (PhotoSwipe)

Same library as Rails (`photoswipe@5` via CDN). Initialize via Alpine `x-init` on the gallery grid container; lazy-import the ESM modules. Photo links use `data-pswp-width`/`-height`/`-caption`.

---

## Phase 8d — Comments (HTMX Append + Alpine UX)

- [ ] `CommentCreateView`: POST validates body, creates Comment, returns rendered `_comment.html` partial
- [ ] `CommentDestroyView`: verifies `comment.user == request.user`, deletes, returns empty 200
- [ ] Form uses `hx-post`, `hx-target="#comments-list"`, `hx-swap="afterbegin"`, `hx-on::after-request="$el.reset(); $data.chars = 0"`
- [ ] Alpine textarea autosize + character counter (`x-data="{ chars: 0 }"`)

---

## Phase 9 — Counter Caches & Concurrency

- [ ] `apps/photos/signals.py`: `post_save`/`post_delete` on `Like` and `Comment` → `Photo.objects.filter(pk=…).update(likes_count=F("likes_count") + 1)`
- [ ] Wire signals via `apps.py` `ready()`
- [ ] Test: 50-thread `ThreadPoolExecutor` calling `get_or_create` → exactly 1 row, count == 1
- [ ] Test: 1000-iteration like/unlike loop → count returns to 0

---

## Phase 10 — Async Pipeline (Deferred)

**Status:** Wire one demo task during Phase 9 to prove the `django.tasks` setup works. Real upload pipeline deferred until uploads ship.

When implemented:
- [ ] `pip install django-tasks-db` (DB-backed, SQLite-friendly)
- [ ] Swap `TASKS["default"]["BACKEND"]` to `"django_tasks_db.backend.DatabaseBackend"`
- [ ] Run worker: `manage.py db_worker` in a separate process / systemd unit
- [ ] `apps/photos/tasks.py`: `@task` `process_upload(upload_id)` — Pillow generates thumbnails

No code changes elsewhere — same `@task` decorator, same `.enqueue()` call site.

---

## Phase 11 — Test Coverage Pass

`python manage.py test` runs everything. Targets:

- [ ] Models: every constraint tested
- [ ] Views: every URL, auth boundary, CSRF
- [ ] Likes: idempotency, counter accuracy, HTMX/JSON variants
- [ ] Auth: signup, login, logout, redirect-when-anonymous
- [ ] Seeds: idempotent counts
- [ ] Concurrency: thread-pool stress (Phase 9)

Stretch: Playwright system tests for optimistic like flip + comment submit + lightbox open. Only if time permits — not load-bearing for the take-home.

---

## Phase 12 — VPS Deployment

**Target:** Hetzner CX22 (~$4/mo) or DO basic droplet ($6/mo). Caddy + gunicorn + systemd + SQLite. ~30 min provisioning.

- [ ] Provision VPS, point DNS at IP
- [ ] `apt install caddy python3.13 python3.13-venv git`
- [ ] Create `app` user; clone to `/opt/clever-gallery`
- [ ] `python3.13 -m venv .venv && pip install -r requirements.txt`
- [ ] Set real env vars in `/etc/clever-gallery.env` (SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, DATABASE_URL — leave default for SQLite)
- [ ] `manage.py migrate && collectstatic --noinput && seed_all`
- [ ] Enable WAL: `sqlite3 db.sqlite3 'PRAGMA journal_mode=WAL;'`
- [ ] `/etc/systemd/system/gunicorn.service` runs `gunicorn config.wsgi:application -w 4 -b 127.0.0.1:8000`
- [ ] `/etc/caddy/Caddyfile`: reverse_proxy to localhost:8000, serve `/static/*` and `/media/*` directly
- [ ] (Optional) litestream → Backblaze B2 for continuous SQLite backup
- [ ] UptimeRobot free tier monitoring `/healthz/`

**Migration off SQLite (when needed):** swap `DATABASE_URL` to Postgres, `manage.py dumpdata > dump.json && loaddata dump.json`. ~30 min of work. Don't pre-build for it.

---

## Scaling Up When Needed

Everything below is **deliberately not built now**. The point of this section is to make it obvious *how* each piece grows up so the take-home reviewer can see the upgrade path is short and the current shape doesn't paint us into a corner. Rule of thumb: don't pay for any of this until a real metric (queue depth, p95, error rate, $/month) demands it.

### Background jobs: `django.tasks` (immediate) → DB worker → Celery + SQS/Redis

The app already uses `django.tasks`'s `@task` decorator + `.enqueue()` API. Three steps up the ladder, each cheap:

1. **Now — `immediate` backend.** Tasks run synchronously in the request process. Zero infra. Fine for the take-home and for the first ~dozen real users. Failure mode: slow uploads block the request thread.
2. **Next — `django-tasks-db` backend.** `pip install django-tasks-db`, add `django_tasks_db` to `INSTALLED_APPS`, run `migrate`, change `TASKS["default"]["BACKEND"]` to `django_tasks_db.backends.DatabaseBackend`, and add a systemd unit running `manage.py db_worker`. **No code changes** — same `@task`/`.enqueue()` calls. Gets you durable retries and out-of-band execution on one box. Good up to roughly thousands of jobs/minute on Postgres or low hundreds on SQLite.
3. **At real scale — Celery + SQS (or Redis).** When you need horizontal worker scale-out, fan-out, scheduled jobs (Celery Beat), priority queues, or visibility into job state across many machines:
   - `pip install "celery[sqs]" boto3` (or `redis` for Redis broker).
   - Add `apps/<app>/celery.py` with the standard `app = Celery("clever", broker=os.getenv("CELERY_BROKER_URL"))` boilerplate; `app.autodiscover_tasks()`.
   - Replace `from django.tasks import task` with `from celery import shared_task` — signature is identical, `@shared_task` everywhere `@task` was. Replace `.enqueue(...)` with `.delay(...)` / `.apply_async(...)`.
   - Run workers under systemd: `celery -A config worker -l info --concurrency=4`. Beat as a separate unit if scheduled jobs land.
   - Pick broker by ops cost: **SQS** if already on AWS (managed, FIFO option, ~$0.40/M messages), **Redis (Elasticache or self-hosted)** if you also need it for caching/rate-limiting/Channels. Avoid RabbitMQ unless someone on the team already runs it.
   - Add `flower` or Celery's built-in events + a Grafana dashboard for queue depth and task latency.

The migration from `django.tasks` to Celery is mostly mechanical because both already enforce the "tasks are top-level functions" + "args are JSON-serializable" discipline. Don't introduce Celery before you have a worker process to justify it — the operational tax (broker, beat, flower, dead-letter handling) is real.

### Database: SQLite → Postgres

SQLite is fine well past where most engineers assume — single-writer, but with WAL mode and a fast disk it handles plenty of read-heavy traffic. Move to Postgres when **any** of these is true:
- You need >1 app server (SQLite doesn't share over the network).
- Write contention shows up as `database is locked` errors.
- You want point-in-time recovery, replication, or managed backups.
- A query benefits from `JSONB`, `GIN` indexes, full-text search, materialized views, or `LISTEN/NOTIFY`.

Migration recipe (~30 min):
1. Provision Postgres (managed: RDS, Neon, Supabase, DO Managed PG; self-hosted: a second VPS with `pg_basebackup` for replicas later).
2. `manage.py dumpdata --natural-foreign --natural-primary --exclude=contenttypes --exclude=auth.permission > dump.json`.
3. Set `DATABASE_URL=postgres://user:pass@host:5432/clever?sslmode=require`. `dj-database-url` already handles this — no settings change.
4. `manage.py migrate && manage.py loaddata dump.json`.
5. Bump `CONN_MAX_AGE` (already 600s) and add `OPTIONS={"sslmode": "require"}` if not encoded in the URL.
6. Install **PgBouncer** (transaction pooling) once you cross ~50 concurrent gunicorn workers — Postgres connections are expensive (~10 MB each); PgBouncer multiplexes them. Point Django at PgBouncer's port instead of Postgres directly.
7. Add a read replica + `DATABASE_ROUTERS` for read-heavy endpoints when one primary stops keeping up.

What stays the same: every model, every query, every test. The ORM hides the engine. The only code that ever cares is migrations using engine-specific features (e.g., `JSONField` indexes, `RunSQL` blocks).

### Caching, sessions, rate limiting

- **Now:** in-memory cache (per-process, lost on restart), DB-backed sessions. Fine for one box.
- **Next:** add Redis. `pip install redis`; set `CACHES["default"] = {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.getenv("REDIS_URL")}`. Switch sessions to `SESSION_ENGINE = "django.contrib.sessions.backends.cache"`. Cache `Photo.srcset()` results, expensive query results, and per-user "did I like?" sets keyed by `(user_id, photo_id_set_hash)`.
- **Rate limiting:** `django-ratelimit` (decorator-based, Redis-backed) on auth endpoints and the comment POST. Keeps a single bored user from flooding the comments table.
- **Per-view caching:** `@cache_page(60)` on the photo grid for anonymous users only (`@vary_on_cookie` is too coarse with auth — use template fragment caching for the per-user "liked" indicator instead).

### Media & images

- **Now:** local filesystem under `MEDIA_ROOT`, served by Whitenoise/Caddy.
- **Next:** S3 (or B2/R2 for cheaper egress) via `django-storages`. Set `STORAGES["default"]["BACKEND"] = "storages.backends.s3.S3Storage"`. Keep static files on Whitenoise — it's already optimal.
- **Image processing pipeline:** Pillow inline is fine for ≤1 MB JPEGs. At real volume, move resizing into a `@task`/Celery job that produces multiple sizes, stores them at `photos/<id>/<size>.webp`, and writes the URLs back to the `Photo` row. The 8 `src_*` methods become DB lookups instead of URL templates against Pexels.
- **CDN:** put CloudFront / BunnyCDN / Cloudflare in front of `MEDIA_URL` and `STATIC_URL` once egress matters. Whitenoise already sets long-cache headers on hashed assets, so CDN integration is one config line.

### Web tier

- **Now:** one VPS, gunicorn sync workers behind Caddy, systemd-managed.
- **Next:** add a second VPS + a load balancer (Caddy on a tiny LB box, or a managed LB). At that point sessions and cache **must** be Redis (no sticky sessions needed) and media **must** be off-box.
- **Workers:** rule of thumb `2 * CPU + 1` sync gunicorn workers; switch to `gunicorn -k uvicorn.workers.UvicornWorker` only if you adopt async views. Add `--max-requests 1000 --max-requests-jitter 100` to recycle workers and bound memory creep.
- **Zero-downtime deploys:** `systemctl reload gunicorn` (gunicorn re-execs gracefully). Run migrations as a separate systemd one-shot before reload; only ever ship backwards-compatible migrations (add column → backfill → flip read path → drop old column over multiple deploys).

### Observability

- **Logs:** structured JSON via `python-json-logger`, shipped to Loki/CloudWatch/Datadog. Add a request-id middleware so a single request is greppable end-to-end through gunicorn → Django → task workers.
- **Metrics:** `django-prometheus` exports per-view latency + DB query counts; scrape with Prometheus, dashboard in Grafana. Track p50/p95/p99 per route, queue depth, worker lag.
- **Errors:** **Sentry** from day one of "real" production. `pip install sentry-sdk[django]`; one `sentry_sdk.init(...)` call. The free tier covers the take-home easily; paid kicks in around real traffic.
- **Uptime:** UptimeRobot or BetterStack hitting `/healthz/` every 60s. Page on 2 consecutive failures.
- **APM (later):** Datadog APM, New Relic, or self-hosted Tempo/Jaeger if request traces across worker boundaries become necessary.

### Security & abuse

- **CSRF / clickjacking / HSTS:** already enabled in the `if not DEBUG:` block.
- **Brute-force login:** add `django-axes` only when login attempt logs show actual abuse. Until then, login throttling via `django-ratelimit` is enough.
- **Content security:** `django-csp` once you stop loading Alpine/HTMX from `unpkg.com` and serve them locally — easier to write a strict CSP when every script is same-origin.
- **Secrets:** `os.getenv` reading from systemd `EnvironmentFile=/etc/clever/env` (mode 0400, owned by `clever:clever`). Graduate to AWS Secrets Manager / Vault once secrets rotate or multiple services share them.
- **Dependency updates:** `pip-audit` in CI; Dependabot/Renovate for PRs.
- **Backups:** SQLite → Litestream replicating to B2 every few seconds. Postgres → managed snapshots + WAL archiving (or `pgbackrest` if self-hosted). Verify restore monthly.

### Frontend

- **Now:** Tailwind v4 standalone CLI (no Node), Alpine + HTMX from `unpkg.com`.
- **Next:** vendor Alpine + HTMX into `static/vendor/` so a CSP can lock down `script-src 'self'` and so `unpkg.com` going down doesn't take the site with it.
- **At scale:** if a real SPA-ish surface lands (e.g., a heavy upload editor), introduce one Vite-built island, not a full SPA rewrite. HTMX + Alpine carry surprisingly far — only break the seal when a specific page demands client-side routing or complex local state.

### Testing & CI

- **Now:** `manage.py test`, run locally and in GitHub Actions.
- **Next:** add Playwright (`pytest-playwright` or standalone) for the optimistic-UI flows (like button, lightbox open/close, comment append) — these can't be verified by request specs alone.
- **Pre-deploy gates:** ruff, black --check, `manage.py check --deploy`, `manage.py makemigrations --check --dry-run`, `manage.py test`. Fail the build on any.
- **Load testing:** `locust` or `k6` against staging before any feature launch that touches a hot path.

### Cost ladder (rough order-of-magnitude)

| Stage | Infra | Monthly | Trigger to graduate |
|---|---|---|---|
| Take-home / ≤10 users | 1 × Hetzner CX22 + Litestream → B2 | ~$5 | First "is the site down?" Slack ping |
| Single-server prod / ≤1k DAU | + managed Postgres (Neon free or DO $15) + Sentry free | ~$20 | Worker process needed, or DB > free tier |
| Multi-server / ≤10k DAU | 2 × app VPS + LB + Postgres + Redis (Upstash free → paid) + S3/B2 + CDN | ~$80 | p95 > 500 ms, or queue lag > 10 s |
| Real scale | Managed K8s or ECS, Celery + SQS, RDS w/ replicas, Datadog | $$$ | Headcount + revenue justifies the ops tax |

The point of the ladder: **every step is reversible and additive**, and nothing in the take-home codebase needs to change to climb it. That's the whole reason for the discipline of "skinny views, fat models, idempotent writes, base Django everywhere."

---

## Out of Scope (explicit non-goals)

- `[-]` django-allauth / Devise — `django.contrib.auth` is sufficient
- `[-]` Custom session model with IP/UA tracking — use `django.contrib.sessions`
- `[-]` Password reset flow
- `[-]` `django-axes` (login throttling) — over-engineering for take-home
- `[-]` Redis — not needed
- `[-]` Celery + SQS — `django.tasks` covers async needs without a broker
- `[-]` S3 / object storage — local filesystem until uploads ship
- `[-]` Real-time broadcasts (Channels / Solid Cable) — HTMX polling if ever needed
- `[-]` `tailwind.config.js` — Tailwind v4 uses CSS-only config
- `[-]` Node toolchain — Tailwind standalone CLI; Alpine + HTMX via CDN
- `[-]` Fly.io — trial expired; deploy to VPS instead
- `[-]` Docker — bare VPS + systemd is simpler at this scale
- `[-]` Settings split (`base/dev/test/prod.py`) — single `settings.py` with `if not DEBUG:`
- `[-]` `django-environ` — `os.getenv` with defaults is enough
- `[-]` pytest / factory_boy — Django's `TestCase` covers the scope
- `[-]` mypy strict / djlint — type hints in new code; templates reviewed by eye
- `[-]` `bin/setup`, `bin/dev`, `bin/ci`, `Procfile.dev`, `honcho` — `manage.py runserver` is the dev command

---

## Intentional Divergences from Rails

| Rails | Django | Why |
|---|---|---|
| `sessions` table with FK to `users`, `ip_address`, `user_agent` | `django_session` (built-in opaque blob) | Use base Django |
| `password_digest` + `has_secure_password` | Django's `password` field + default hasher | Native, equivalent |
| `email_address` column | `email` column | Django convention |
| `passwords` controller (token-based reset) | omitted | Out of scope |
| Solid Cable WebSocket broadcasts | omitted | HTMX polling if ever needed |
| Turbo Streams via `*.turbo_stream.erb` | HTMX partial swaps via `_*.html` partials | Same shape, different transport |
| Stimulus controllers | Alpine `x-data` + `x-init` | More idiomatic for declarative-in-template state |
| Foreman (`bin/dev`) | `manage.py runserver` | Frontend toolchain (Tailwind watcher) added in Phase 2 via two terminals or `concurrently`-equivalent if needed |
| Solid Queue / Solid Cache | Django 6.0 native `django.tasks` (immediate backend now; `django-tasks-db` later) | One DB, no broker |
| Thruster + Puma | Caddy + Gunicorn | Battle-tested, simpler |
| Minitest + Capybara/Selenium | Django `TestCase` (+ Playwright if time allows) | Built-in is enough |
| Fly.io | VPS + Caddy + systemd | Trial expired |

---

## Open Questions / Decision Log

Format: `YYYY-MM-DD — Question — Resolution`.

- 2026-05-14 — Stack lock-in v1: SQLite, HTMX + Alpine, base Django, defer Celery+SQS, split settings, django-environ, full bin/ scripts, axes, pytest. — Superseded by simplification round.
- 2026-05-14 — Background jobs without an SQS account: Celery sync mode vs. django-tasks vs. defer. — **Django 6.0 native `django.tasks` with `immediate` backend.** Same API as a real worker; swap to `django-tasks-db` when a worker process is needed.
- 2026-05-14 — Settings split, env loader, bin/ scripts, axes, pytest. — **Stripped.** Take-home doesn't need them. Single `settings.py`, `os.getenv`, `manage.py runserver`, `manage.py test`.
- 2026-05-14 — SQLite-only vs. Postgres-optional. — **`dj-database-url`**: SQLite default, `DATABASE_URL=postgres://…` switches.
- 2026-05-14 — Django 5.2 LTS vs. 6.0. — **Django 6.0** (latest stable; ships native `django.tasks`).
