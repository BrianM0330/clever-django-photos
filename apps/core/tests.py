from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class HealthzViewTests(TestCase):
    def test_healthz_returns_200_json_ok(self) -> None:
        response = self.client.get(reverse("core:healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class LandingViewTests(TestCase):
    """Smoke + content tests for the marketing landing page.

    Covers two concerns:
      1. The base layout pipeline still wires up correctly — Tailwind
         stylesheet, Alpine + HTMX CDN scripts, CSRF token for HTMX POSTs.
      2. The ported Rails landing markup renders, with the auth-aware
         navbar + hero CTAs flipping correctly between anonymous and
         authenticated users.
    """

    def test_landing_renders_with_frontend_toolchain(self) -> None:
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "core/landing.html")

        body = response.content.decode()
        self.assertIn("/static/css/app.css", body)
        self.assertIn("alpinejs", body)
        self.assertIn("https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js", body)
        self.assertIn("https://cdn.jsdelivr.net/npm/htmx-ext-ws@2.0.4", body)
        self.assertIn("X-CSRFToken", body)

    def test_app_js_keeps_like_button_state_local(self) -> None:
        app_js_path = finders.find("js/app.js")
        self.assertIsNotNone(app_js_path)

        with open(app_js_path) as app_js:
            body = app_js.read()

        self.assertNotIn('Alpine.store("likeRealtime"', body)
        self.assertNotIn("new WebSocket", body)
        self.assertIn('Alpine.data("likeButton"', body)
        self.assertIn("toggle()", body)
        self.assertIn("this.liked = !this.liked", body)

    def test_toast_css_is_themed_and_positioned(self) -> None:
        css_path = finders.find("css/app.css")
        self.assertIsNotNone(css_path)

        with open(css_path) as css_file:
            css = css_file.read()

        self.assertIn(".toast-region", css)
        self.assertIn("position: fixed", css)
        self.assertIn(".toast-card", css)

    def test_landing_anonymous_shows_signup_and_signin_ctas(self) -> None:
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "Join the network")
        self.assertContains(response, "Sign in to your gallery")
        self.assertContains(response, f'href="{reverse("accounts:signup")}"')
        self.assertContains(response, f'href="{reverse("accounts:login")}"')
        self.assertNotContains(response, "View the collection")
        # Navbar CTAs for anonymous visitors.
        self.assertContains(response, ">Sign in<")
        self.assertContains(response, ">Sign up<")
        self.assertNotContains(response, ">Sign out<")
        self.assertNotContains(response, ">Discover<")
        self.assertNotContains(response, ">Photos<")
        self.assertNotContains(response, ">Moods<")
        self.assertNotContains(response, ">Social<")

    def test_landing_authenticated_shows_gallery_cta(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(username="brian", password="password")
        self.client.force_login(user)

        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "View the collection")
        self.assertContains(response, f'href="{reverse("photos:index")}"')
        self.assertContains(response, f'action="{reverse("accounts:logout")}"')
        self.assertNotContains(response, "Join the network")
        # Navbar CTAs for authenticated users.
        self.assertContains(response, ">B</abbr>")
        self.assertContains(response, ">Sign out<")
        self.assertNotContains(response, ">Sign in<")
        self.assertNotContains(response, ">Discover<")
        self.assertNotContains(response, ">Photos<")
        self.assertNotContains(response, ">Moods<")
        self.assertNotContains(response, ">Social<")

    def test_landing_includes_hero_illustration_and_animation_hooks(self) -> None:
        """Catches regressions where the SVG illustration or its animation
        utilities (defined in assets/css/input.css) get accidentally dropped."""
        response = self.client.get(reverse("core:landing"))
        body = response.content.decode()
        self.assertIn("mask-glow-sweep", body)
        self.assertIn("animate-draw", body)
        self.assertIn("delay-600", body)
