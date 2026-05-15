# Photo Gallery (Django)

🚀 **Live Demo:** <https://clever-django-gallery.bmendo.dev/>

A full-stack photo gallery application built with Django 6.0, HTMX, and Alpine.js.

A port of the Rails 8.1 + Hotwire reference under `TEMP_RAILS_REFERENCE/rails-hotwire-trial/`.
Same feature surface (auth, gallery, likes, comments, lightbox), different stack — chosen to maximize what ships in stock Django and minimize third-party dependencies.

## Tech Stack

- **Python** 3.12+ / **Django** 6.0
- **SQLite** (Default) / **Postgres** (Opt-in via `DATABASE_URL`)
- **HTMX 2.0** — Server-rendered HTML partial swaps (our Turbo Streams analog)
- **Alpine.js 3** — For optimistic UI and small client-side interactivity
- **Tailwind CSS v4** — Via standalone CLI binary (no Node.js required)
- **Daphne + Channels** — For ASGI HTTP and realtime WebSockets
- **`django.tasks`** — Native background workers (new in Django 6.0)
- **PhotoSwipe 5** — CDN-loaded lightbox

## Local Setup

Getting the database and environment ready is straightforward using `make` commands.

```bash
git clone <repo-url>
cd clever-django-gallery
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

To run migrations and seed the database with initial photos and test accounts:

```bash
make db-setup
```

_(Note: `make db-setup` runs both `migrate` and `seed_all`. It is fully idempotent and safe to run multiple times)._

## Running the App

One command runs both Django and the Tailwind CSS watcher:

```bash
bin/dev
```

Open [http://localhost:8000](http://localhost:8000)

## Test Accounts

The seed command creates a predictable database state with the following test users:

| Username | Password |
| -------- | -------- |
| brian    | password |
| ryan     | password |
| jake     | password |
| mike     | password |
| admin    | password |

_(Note: If testing email integrations, assume `<username>@clever.com`)_

## Running Tests

This application maintains the same strong testing culture as the Rails reference application.

```bash
python manage.py test           # Run the full suite
python manage.py test apps.core # Run one specific app
python manage.py check          # Config sanity check
```

## Architecture & Assignment Requirements

This project is a Python port of a take-home assignment originally targeting Rails. Here is how I approached the requirements and the architectural decisions behind them:

### Authentication

For authentication, I stuck with Django's built-in `django.contrib.auth` using the stock `User` model (username and password). I intentionally avoided heavy third-party packages like Allauth or JWTs because a simple session-based system is more than enough for this scope. The app strictly gates access out of the box and redirects unauthenticated users exactly as requested.

**Bonus:** I built an idempotent `seed_all` management command that sets up five test accounts for easy QA, and I also enabled a full sign-up flow so external reviewers can easily interact with the live demo.

### Database Design & Gallery

The gallery displays the 10 photos required from the CSV, but I wanted to ensure data integrity was bulletproof at the database layer first. The `seed_all` command parses the CSV directly into SQLite, and to enforce the "one like per user" rule, I didn't just rely on basic form validation. I used `Like.objects.get_or_create()` paired with a strict `UniqueConstraint` on the database level to guarantee idempotent writes.

**Bonus (Database Optimization):** Instead of storing all those messy image variant URLs from the CSV, the database only stores the base URL. The `Photo` model dynamically generates responsive `src` queries on the fly, keeping the database footprint tiny.
**Bonus (Performance):** I added counter caches via Django signals to automatically update `likes_count` and `comments_count` on the `Photo` model, completely eliminating N+1 queries when rendering the gallery feed.
**Bonus (Lightbox):** To round out the frontend experience, I wired up PhotoSwipe 5 to provide a proper mobile-friendly lightbox instead of just a static image grid.

### Interactivity (No JS Frameworks)

The prompt asked for no React, Vue, or SPAs, so I leaned fully into the hypermedia philosophy. I replaced the suggested Rails Hotwire stack with HTMX to handle seamless, no-reload partial HTML swaps for likes and comments. To keep the markup clean, I injected the CSRF token globally in the base template so individual HTMX tags don't get cluttered with payloads.

**Bonus (Optimistic UI):** I sprinkled in Alpine.js strictly for declarative, isolated state flips. When you click 'like', Alpine instantly toggles the visual icon state before the server even responds, giving the app a zero-latency feel.
**Bonus (Realtime):** I wired up Daphne and Django Channels. Now, when any user likes a photo, the backend counter cache updates and broadcasts that new count via WebSockets to everyone else viewing the gallery in realtime.
**Bonus (Accessibility and Mobile)** - I feel like this is table stakes for webapps in an AI era but it should be decent and/or good!

### Extra Features I'd Add Next

If I had another week on this, I would build:

- Image Upload - Filesystem based uploads. Maybe upload to S3 but would have to make a personal AWS account....
- Photograph "ownership" between users and photos. Maybe a role for "photographer" or something. Could get complex
- Email service. Self explanatory - cumbersome. Not sure if I wanted to handle this in the 72h window
- **Image Auto-Tagging:** Using an asynchronous Celery task and a lightweight ML model to automatically tag uploaded images.
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
