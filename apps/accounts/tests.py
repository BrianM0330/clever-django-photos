from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthFlowTests(TestCase):
    def test_auth_settings_match_phase_4_routes(self):
        self.assertEqual(settings.LOGIN_URL, reverse("accounts:login"))
        self.assertEqual(settings.LOGIN_REDIRECT_URL, reverse("photos:index"))
        self.assertEqual(settings.LOGOUT_REDIRECT_URL, reverse("core:landing"))

    def test_login_page_renders_signup_link_and_form(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertContains(response, "Sign in to your gallery")
        self.assertContains(response, f'href="{reverse("accounts:signup")}"')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_signup_page_renders_login_link_and_form(self):
        response = self.client.get(reverse("accounts:signup"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertContains(response, "Create your account")
        self.assertContains(response, f'href="{reverse("accounts:login")}"')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')

    def test_signup_creates_user_logs_in_and_redirects_to_photos(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "brian",
                "password1": "strong-password-123",
                "password2": "strong-password-123",
            },
        )

        self.assertRedirects(response, reverse("photos:index"), fetch_redirect_response=False)
        user = get_user_model().objects.get(username="brian")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_with_duplicate_username_rerenders_with_error(self):
        get_user_model().objects.create_user(username="brian", password="password")

        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "brian",
                "password1": "strong-password-123",
                "password2": "strong-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertContains(response, "A user with that username already exists")
        self.assertEqual(get_user_model().objects.filter(username="brian").count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_signup_with_mismatched_passwords_rerenders_with_error(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "brian",
                "password1": "strong-password-123",
                "password2": "different-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertContains(response, "The two password fields didn’t match")
        self.assertFalse(get_user_model().objects.filter(username="brian").exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_with_wrong_password_rerenders_with_error(self):
        get_user_model().objects.create_user(username="brian", password="password")

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "brian", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_with_correct_password_redirects_to_photos(self):
        user = get_user_model().objects.create_user(username="brian", password="password")

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "brian", "password": "password"},
        )

        self.assertRedirects(response, reverse("photos:index"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_logout_redirects_to_root_and_clears_session(self):
        user = get_user_model().objects.create_user(username="brian", password="password")
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("core:landing"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_photos_redirects_to_login_when_logged_out(self):
        response = self.client.get(reverse("photos:index"))

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('photos:index')}")

    def test_photos_renders_for_logged_in_user(self):
        user = get_user_model().objects.create_user(username="brian", password="password")
        self.client.force_login(user)

        response = self.client.get(reverse("photos:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photos/photo_list.html")
        self.assertContains(response, "All Photos")
