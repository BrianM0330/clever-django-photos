# Photo Gallery (Django)

🚀 **Live Demo:** <https://clever-django-gallery.bmendo.dev/>

A full-stack photo gallery built with Django 6.0, HTMX, Alpine.js, Tailwind v4, and SQLite.

This is a Django port of the Rails 8.1 + Hotwire reference under `TEMP_RAILS_REFERENCE/rails-hotwire-trial/`. The point was not to turn it into a SPA or hide the server behind JSON. I wanted the Django version to keep the same hypermedia shape as the Rails app: server-rendered pages, small HTML partial swaps, durable database state, and boring setup commands.

## Reviewer Quickstart

Install Python deps:

```bash
git clone <repo-url>
cd clever-django-gallery
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Create the database, run migrations, and seed the app:

```bash
make db-setup
```

`make db-setup` runs `migrate` and `seed_all`. It is idempotent and safe to run more than once.

Run the app:

```bash
bin/dev
```

Open [http://localhost:8000](http://localhost:8000). `bin/dev` runs Daphne and the Tailwind watcher together through `honcho`. If you want the plain Django server instead, use `make server`.

## Test Accounts

The seed command creates a predictable database state with 10 photos and these users:

| Username | Password |
| -------- | -------- |
| brian    | password |
| ryan     | password |
| jake     | password |
| mike     | password |
| admin    | password |

If testing email-adjacent flows later, assume `<username>@clever.com`.

## Running Tests

```bash
make test              # Run the full Django test suite
make check             # Run Django's system checks
python manage.py test  # Same test runner without Make
```

For focused runs, Django's built-in runner works well:

```bash
python manage.py test apps.photos
python manage.py test apps.accounts
python manage.py test apps.core
```

## Tech Stack

- **Python** 3.13 / **Django** 6.0
- **SQLite** by default / **Postgres** opt-in via `DATABASE_URL`
- **HTMX 2.0** for server-rendered HTML swaps, the Django equivalent of Turbo Frames/Streams here
- **Alpine.js 3** for tiny local UI state like optimistic button feedback and copy-to-clipboard
- **Tailwind CSS v4** through the standalone binary, no Node toolchain
- **Daphne + Channels** for ASGI HTTP and realtime like-count broadcasts
- **`django.tasks`** with the immediate backend for future background work
- **PhotoSwipe 5** for a mobile-friendly lightbox

## Architecture & Assignment Requirements

This project is a Python port of a take-home assignment originally targeting Rails. Here is how I approached the requirements and the architectural decisions behind them.

### Authentication

For authentication, I stuck with Django's built-in `django.contrib.auth` using the stock `User` model (username and password). I intentionally avoided heavy third-party packages like Allauth or JWTs because a simple session-based system is more than enough for this scope. The app strictly gates access out of the box and redirects unauthenticated users exactly as requested.

**Bonus:** I built an idempotent `seed_all` management command that sets up five test accounts for easy QA, and I also enabled a full sign-up flow so external reviewers can easily interact with the live demo.

### Database Design & Gallery

The gallery displays the 10 photos required from the CSV, but I wanted to ensure data integrity was bulletproof at the database layer first. The `seed_all` command parses the CSV directly into SQLite. To enforce the "one like per user" rule, I didn't just rely on button state or form validation. I used `Like.objects.get_or_create()` paired with a strict `UniqueConstraint` on `(user, photo)` so duplicate like attempts collapse to one durable row.

**Bonus (Database Optimization):** Instead of storing all those messy image variant URLs from the CSV, the database only stores the base URL. The `Photo` model dynamically generates responsive `src` queries on the fly, keeping the database footprint tiny.
**Bonus (Performance):** I added counter caches via Django signals with `F()` expressions to update `likes_count` and `comments_count` on the `Photo` model. The gallery does not need to count related rows for every card render.
**Bonus (Lightbox):** To round out the frontend experience, I wired up PhotoSwipe 5 to provide a proper mobile-friendly lightbox instead of just a static image grid.

### Like Semantics & Race Conditions

The star reflects whether the current signed-in user liked the photo, not whether the photo has any likes. The list view precomputes the current user's liked photo IDs in one query and annotates each in-memory photo object before rendering. Duplicate POSTs are idempotent, DELETE is idempotent, and the database still has the final say through the unique constraint.

Counter cache updates use database-side `F()` expressions instead of read-modify-write Python arithmetic. There is also a threaded concurrency test around `get_or_create()` that proves 50 competing like attempts create one row and increment the counter once. SQLite being singel writer might cause issues

### Interactivity (No JS Frameworks)

The prompt asked for no React, Vue, or SPAs, so I leaned fully into the hypermedia philosophy. I replaced the suggested Rails Hotwire stack with HTMX to handle seamless, no-reload partial HTML swaps for likes and comments. I put the CSRF token in the root as well to make things neat add

**Bonus (Optimistic UI):** I sprinkled in Alpine.js strictly for declarative, isolated state flips. When you click 'like', Alpine instantly toggles the visual icon state before the server even responds, giving the app a zero-latency feel.
**Bonus (Realtime):** I wired up Daphne and Django Channels. Now, when any user likes a photo, the backend counter cache updates and broadcasts that new count via WebSockets to everyone else viewing the gallery in realtime.
**Bonus (Accessibility and Mobile)** - I feel like this is table stakes for webapps in an AI era but it should be decent and/or good!

### Testing

The test suite uses Django's built-in `TestCase` and `Client`. I added tests for the real product and data-integrity paths: signup/login/logout, auth redirects, seeded data idempotency, model constraints, current-user like state, duplicate like prevention, unlike behavior, HTMX partial rendering, no-JS form fallback, counter caches, realtime like-count broadcasts, and a threaded race-condition test for likes.

### Extra Features I'd Add Next

If I had another week on this, I would build:

- Comments UI - the model, endpoints, HTMX partials, and tests are in place, but I would polish the visible detail-page commenting experience before calling it part of the MVP.
- Image Upload - Filesystem based uploads. Maybe upload to S3 but would have to make a personal AWS account....
- Photograph "ownership" between users and photos. Maybe a role for "photographer" or something. Could get complex
- Email service. Self explanatory - cumbersome. Not sure if I wanted to handle this in the 72h window
- **Image Auto-Tagging:** Using an asynchronous background task and a lightweight ML model to automatically tag uploaded images.
- **Social Sharing:** A generic sharing HTMX modal with OpenGraph meta tags generation for distinct photos.
- **User Profiles:** A lightweight public profile page showing an activity feed of what a user has liked and uploaded.

## Scaling Up (from a single VPS)

While this currently runs beautifully on a single $6 VPS, the architecture is designed to scale horizontally without massive rewrites. These steps mirror how the Rails reference app scales.

1. **Background Workers:** We are currently using the in-process `immediate` backend for `django.tasks`. Upgrading simply means swapping the backend to `django-tasks-db` (or Celery/SQS for massive scale). The call sites (`@task`) remain completely identical.
2. **Database:** SQLite in WAL mode handles surprising volume, but `dj-database-url` lets us switch to Postgres instantly by just updating the `DATABASE_URL` environment variable.
3. **Realtime / WebSockets:** We use the `InMemoryChannelLayer` for Channels right now. If we scale up to multiple ASGI workers, we drop in `channels-redis` so WebSocket broadcasts hit all instances.
4. **Media & Assets:** Uploads currently hit the local disk. Scaling up means dropping in `django-storages` and pointing `MEDIA_URL` (and potentially `STATIC_URL`) at an object store like S3 or Cloudflare R2, paired with a CDN.
5. **Caching:** If gallery views become expensive, adding Redis and configuring Django's cache framework (`CACHES` setting) would allow us to cache rendered template fragments or expensive queries.

## Deployment

The Django app is deployed on a DigitalOcean VPS supervised by `systemd`, sitting behind a **Caddy** reverse proxy for automatic TLS and static file serving. There is intentionally no Docker or Kubernetes involved—it's the simplest production setup that handles TLS, log rotation, and crash recovery perfectly.

You can view the live Django app here:
<https://clever-django-gallery.bmendo.dev/>
