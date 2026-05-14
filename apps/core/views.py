"""Core views — healthcheck + landing placeholder."""

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render


def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness probe. Returns 200 + JSON. No DB hit."""
    return JsonResponse({"status": "ok"})


def landing(request: HttpRequest):
    """Marketing landing page. Real content lands with templates in Phase 7;
    for Phase 2 this just proves the base layout + Tailwind + Alpine + HTMX
    pipeline renders end-to-end."""
    return render(request, "core/landing.html")
