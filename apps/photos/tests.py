from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from time import sleep
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, OperationalError, close_old_connections, transaction
from django.db.models import Sum
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.photos.consumers import PhotoLikesConsumer
from apps.photos.models import Comment, Like, Photo
from apps.photos.realtime import photo_likes_group_name


class GalleryModelTests(TestCase):
    def test_unique_user_photo_like_constraint_enforced(self):
        user = self.create_user()
        photo = self.create_photo()
        Like.objects.create(user=user, photo=photo)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Like.objects.create(user=user, photo=photo)

    def test_like_create_and_delete_updates_photo_counter(self):
        user = self.create_user()
        photo = self.create_photo()

        like = Like.objects.create(user=user, photo=photo)
        photo.refresh_from_db()
        self.assertEqual(photo.likes_count, 1)

        like.delete()
        photo.refresh_from_db()
        self.assertEqual(photo.likes_count, 0)

    def test_photo_pexels_id_unique_constraint_enforced(self):
        self.create_photo(pexels_id=21_751_820)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_photo(pexels_id=21_751_820)

    def test_comment_body_max_length_1000(self):
        comment = Comment(user=self.create_user(), photo=self.create_photo(), body="x" * 1001)

        with self.assertRaises(ValidationError):
            comment.full_clean()

    def test_comment_body_cannot_be_blank(self):
        comment = Comment(user=self.create_user(), photo=self.create_photo(), body="   ")

        with self.assertRaises(ValidationError):
            comment.full_clean()

    def test_comment_body_strips_whitespace_on_save(self):
        comment = Comment.objects.create(user=self.create_user(), photo=self.create_photo(), body="  Great shot  ")

        self.assertEqual(comment.body, "Great shot")

    def test_comment_create_and_delete_updates_photo_counter(self):
        comment = Comment.objects.create(user=self.create_user(), photo=self.create_photo(), body="Great shot")
        photo = comment.photo
        photo.refresh_from_db()
        self.assertEqual(photo.comments_count, 1)

        comment.delete()
        photo.refresh_from_db()
        self.assertEqual(photo.comments_count, 0)

    def test_photo_dimensions_must_be_greater_than_zero(self):
        photo = self.build_photo(width=0)

        with self.assertRaises(ValidationError):
            photo.full_clean()

    def test_photo_positive_fields_are_database_constrained(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_photo(width=0)

    def test_photo_src_large_matches_pexels_pattern(self):
        photo = self.build_photo(pexels_id=21_751_820)

        self.assertEqual(
            photo.src_large,
            "https://images.pexels.com/photos/21751820/pexels-photo-21751820.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        )

    def test_photo_src_helpers_match_rails_reference(self):
        photo = self.build_photo(pexels_id=21_751_820)
        base_url = "https://images.pexels.com/photos/21751820/pexels-photo-21751820.jpeg"

        self.assertEqual(photo.src_original, base_url)
        self.assertEqual(photo.src_large2x, f"{base_url}?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940")
        self.assertEqual(photo.src_landscape, f"{base_url}?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200")
        self.assertEqual(
            photo.srcset,
            {
                photo.src_medium: "350w",
                photo.src_large: "940w",
                photo.src_large2x: "1880w",
            },
        )

    def test_orientation_querysets_use_dimensions(self):
        portrait = self.create_photo(pexels_id=21_751_820, width=3888, height=5184)
        landscape = self.create_photo(pexels_id=21_405_575, width=5284, height=3514)

        self.assertIn(portrait, Photo.portrait())
        self.assertNotIn(landscape, Photo.portrait())
        self.assertIn(landscape, Photo.landscape())
        self.assertNotIn(portrait, Photo.landscape())

    def test_liked_ids_for_returns_current_users_likes_only(self):
        user = self.create_user(username="brian")
        other_user = self.create_user(username="ryan")
        liked_photo = self.create_photo(pexels_id=21_751_820)
        other_photo = self.create_photo(pexels_id=21_405_575)
        unliked_photo = self.create_photo(pexels_id=21_294_736)
        Like.objects.create(user=user, photo=liked_photo)
        Like.objects.create(user=other_user, photo=other_photo)

        liked_ids = Photo.liked_ids_for(user, [liked_photo, other_photo, unliked_photo])

        self.assertEqual(liked_ids, {liked_photo.pk})

    def test_liked_ids_for_anonymous_user_returns_empty_set(self):
        photo = self.create_photo()

        self.assertEqual(Photo.liked_ids_for(AnonymousUser(), [photo]), set())

    def test_liked_by_checks_current_user_only(self):
        user = self.create_user(username="brian")
        other_user = self.create_user(username="ryan")
        photo = self.create_photo()
        Like.objects.create(user=other_user, photo=photo)

        self.assertFalse(photo.liked_by(user))
        self.assertTrue(photo.liked_by(other_user))
        self.assertFalse(photo.liked_by(AnonymousUser()))

    def test_like_create_for_is_idempotent(self):
        user = self.create_user()
        photo = self.create_photo()

        first_like, first_created = Like.create_for(user=user, photo=photo)
        second_like, second_created = Like.create_for(user=user, photo=photo)
        photo.refresh_from_db()

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_like, second_like)
        self.assertEqual(Like.objects.filter(user=user, photo=photo).count(), 1)
        self.assertEqual(photo.likes_count, 1)

    def test_like_delete_for_is_idempotent(self):
        user = self.create_user()
        photo = self.create_photo()
        Like.objects.create(user=user, photo=photo)

        first_deleted = Like.delete_for(user=user, photo=photo)
        second_deleted = Like.delete_for(user=user, photo=photo)
        photo.refresh_from_db()

        self.assertEqual(first_deleted, 1)
        self.assertEqual(second_deleted, 0)
        self.assertFalse(Like.objects.filter(user=user, photo=photo).exists())
        self.assertEqual(photo.likes_count, 0)

    def test_comment_create_for_validates_strips_and_updates_counter(self):
        user = self.create_user()
        photo = self.create_photo()

        comment = Comment.create_for(user=user, photo=photo, body="  Great shot  ")
        photo.refresh_from_db()

        self.assertEqual(comment.body, "Great shot")
        self.assertEqual(photo.comments_count, 1)

    def test_comment_create_for_rejects_invalid_body(self):
        user = self.create_user()
        photo = self.create_photo()

        with self.assertRaises(ValidationError):
            Comment.create_for(user=user, photo=photo, body="   ")

        self.assertFalse(Comment.objects.exists())

    def create_user(self, username="brian"):
        return get_user_model().objects.create_user(username=username, password="password")

    def build_photo(self, **attributes):
        defaults = {
            "pexels_id": 21_751_820,
            "width": 3888,
            "height": 5184,
            "url": "https://www.pexels.com/photo/example-21751820/",
            "photographer": "Felix",
            "photographer_url": "https://www.pexels.com/@felix",
            "photographer_id": 21_751_820,
            "avg_color": "#333831",
            "alt": "A small island surrounded by trees in the middle of a lake",
        }
        defaults.update(attributes)
        return Photo(**defaults)

    def create_photo(self, **attributes):
        photo = self.build_photo(**attributes)
        photo.save()
        return photo


class RealtimeLikeTests(TransactionTestCase):
    def test_authenticated_socket_receives_initial_like_count(self):
        user = self.create_user()
        photo = self.create_photo(likes_count=2)

        message = async_to_sync(self.receive_initial_message)(user, photo)

        self.assertIn(f'id="photo-{photo.pk}-like_count"', message)
        self.assertIn('hx-swap-oob="true"', message)
        self.assertIn(">2</span>", message)

    def test_anonymous_socket_is_rejected(self):
        photo = self.create_photo()

        connected = async_to_sync(self.connect_anonymous)(photo)

        self.assertFalse(connected)

    def test_socket_receives_broadcast_like_count(self):
        user = self.create_user()
        photo = self.create_photo(likes_count=1)

        message = async_to_sync(self.receive_broadcast_message)(user, photo, likes_count=4)

        self.assertIn(f'id="photo-{photo.pk}-like_count"', message)
        self.assertIn('hx-swap-oob="true"', message)
        self.assertIn(">4</span>", message)

    def test_observer_who_liked_receives_other_user_like_increment(self):
        observer = self.create_user(username="brian")
        actor = self.create_user(username="ryan")
        photo = self.create_photo()
        Like.objects.create(user=observer, photo=photo)
        photo.refresh_from_db()

        messages = async_to_sync(self.receive_messages_after_view_actions)(
            observer,
            photo,
            [("post", actor)],
        )
        photo.refresh_from_db()

        self.assertEqual(messages, [1, 2])
        self.assertTrue(Like.objects.filter(user=observer, photo=photo).exists())
        self.assertTrue(Like.objects.filter(user=actor, photo=photo).exists())
        self.assertEqual(photo.likes_count, 2)

    def test_observer_who_liked_receives_other_user_unlike_decrement(self):
        observer = self.create_user(username="brian")
        actor = self.create_user(username="ryan")
        photo = self.create_photo()
        Like.objects.create(user=observer, photo=photo)
        Like.objects.create(user=actor, photo=photo)
        photo.refresh_from_db()

        messages = async_to_sync(self.receive_messages_after_view_actions)(
            observer,
            photo,
            [("delete", actor)],
        )
        photo.refresh_from_db()

        self.assertEqual(messages, [2, 1])
        self.assertTrue(Like.objects.filter(user=observer, photo=photo).exists())
        self.assertFalse(Like.objects.filter(user=actor, photo=photo).exists())
        self.assertEqual(photo.likes_count, 1)

    def test_observer_who_liked_receives_other_user_like_then_unlike_sequence(self):
        observer = self.create_user(username="brian")
        actor = self.create_user(username="ryan")
        photo = self.create_photo()
        Like.objects.create(user=observer, photo=photo)
        photo.refresh_from_db()

        messages = async_to_sync(self.receive_messages_after_view_actions)(
            observer,
            photo,
            [("post", actor), ("delete", actor)],
        )
        photo.refresh_from_db()

        self.assertEqual(messages, [1, 2, 1])
        self.assertTrue(Like.objects.filter(user=observer, photo=photo).exists())
        self.assertFalse(Like.objects.filter(user=actor, photo=photo).exists())
        self.assertEqual(photo.likes_count, 1)

    async def receive_initial_message(self, user, photo):
        communicator = self.communicator_for(user, photo)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        message = await communicator.receive_from()
        await communicator.disconnect()
        return message

    async def connect_anonymous(self, photo):
        communicator = self.communicator_for(AnonymousUser(), photo)
        connected, _ = await communicator.connect()
        await communicator.disconnect()
        return connected

    async def receive_broadcast_message(self, user, photo, *, likes_count):
        communicator = self.communicator_for(user, photo)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_from()

        await get_channel_layer().group_send(
            photo_likes_group_name(photo.pk),
            {
                "type": "photo.like_count",
                "photo_id": photo.pk,
                "likes_count": likes_count,
            },
        )
        message = await communicator.receive_from()
        await communicator.disconnect()
        return message

    async def receive_messages_after_view_actions(self, observer, photo, actions):
        communicator = self.communicator_for(observer, photo)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        messages = [self.extract_like_count(await communicator.receive_from())]
        for method, actor in actions:
            response_status = await self.perform_like_request(method, actor, photo)
            self.assertEqual(response_status, 200)
            messages.append(self.extract_like_count(await communicator.receive_from()))

        await communicator.disconnect()
        return messages

    @database_sync_to_async
    def perform_like_request(self, method, user, photo):
        self.client.force_login(user)
        url = reverse("photos:like_toggle", kwargs={"pk": photo.pk})
        if method == "post":
            response = self.client.post(url)
        elif method == "delete":
            response = self.client.delete(url)
        else:
            raise ValueError(f"Unsupported like request method: {method}")

        return response.status_code

    def communicator_for(self, user, photo):
        communicator = WebsocketCommunicator(PhotoLikesConsumer.as_asgi(), f"/ws/photos/{photo.pk}/likes/")
        communicator.scope["user"] = user
        communicator.scope["url_route"] = {"kwargs": {"photo_id": photo.pk}}
        return communicator

    def extract_like_count(self, html):
        return int(html.split("</span>", 1)[0].rsplit(">", 1)[1])

    def create_user(self, username="brian"):
        return get_user_model().objects.create_user(username=username, password="password")

    def build_photo(self, **attributes):
        defaults = {
            "pexels_id": 21_751_820,
            "width": 3888,
            "height": 5184,
            "url": "https://www.pexels.com/photo/example-21751820/",
            "photographer": "Felix",
            "photographer_url": "https://www.pexels.com/@felix",
            "photographer_id": 21_751_820,
            "avg_color": "#333831",
            "alt": "A small island surrounded by trees in the middle of a lake",
        }
        defaults.update(attributes)
        return Photo(**defaults)

    def create_photo(self, **attributes):
        photo = self.build_photo(**attributes)
        photo.save()
        return photo


class CounterCacheConcurrencyTests(TransactionTestCase):
    def test_concurrent_like_get_or_create_creates_one_row_and_increments_counter_once(self):
        user = self.create_user()
        photo = self.create_photo()
        user_id = user.pk
        photo_id = photo.pk

        def create_like():
            close_old_connections()
            try:
                for attempt in range(100):
                    try:
                        Like.objects.get_or_create(user_id=user_id, photo_id=photo_id)
                        return
                    except OperationalError:
                        close_old_connections()
                        if attempt == 99:
                            raise
                        sleep(0.02)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=50) as executor:
            list(executor.map(lambda _index: create_like(), range(50)))

        photo.refresh_from_db()
        self.assertEqual(Like.objects.filter(user=user, photo=photo).count(), 1)
        self.assertEqual(photo.likes_count, 1)

    def test_repeated_like_unlike_loop_returns_counter_to_zero(self):
        user = self.create_user()
        photo = self.create_photo()

        for _index in range(1000):
            Like.create_for(user=user, photo=photo)
            Like.delete_for(user=user, photo=photo)

        photo.refresh_from_db()
        self.assertFalse(Like.objects.filter(user=user, photo=photo).exists())
        self.assertEqual(photo.likes_count, 0)

    def create_user(self, username="brian"):
        return get_user_model().objects.create_user(username=username, password="password")

    def build_photo(self, **attributes):
        defaults = {
            "pexels_id": 21_751_820,
            "width": 3888,
            "height": 5184,
            "url": "https://www.pexels.com/photo/example-21751820/",
            "photographer": "Felix",
            "photographer_url": "https://www.pexels.com/@felix",
            "photographer_id": 21_751_820,
            "avg_color": "#333831",
            "alt": "A small island surrounded by trees in the middle of a lake",
        }
        defaults.update(attributes)
        return Photo(**defaults)

    def create_photo(self, **attributes):
        photo = self.build_photo(**attributes)
        photo.save()
        return photo


class SeedAllCommandTests(TestCase):
    def test_seed_all_creates_expected_counts(self):
        call_command("seed_all", stdout=StringIO())

        self.assertEqual(Photo.objects.count(), 10)
        self.assertEqual(get_user_model().objects.count(), 5)
        self.assertEqual(Like.objects.count(), 30)
        self.assertEqual(Comment.objects.count(), 13)
        self.assertEqual(Photo.objects.aggregate(total=Sum("likes_count"))["total"], 30)
        self.assertEqual(Photo.objects.aggregate(total=Sum("comments_count"))["total"], 13)
        self.assertEqual(Photo.objects.get(pexels_id=21_315_872).likes_count, 5)
        self.assertEqual(Photo.objects.get(pexels_id=21_294_950).comments_count, 3)
        self.assertEqual(
            list(get_user_model().objects.order_by("username").values_list("username", flat=True)),
            ["admin", "brian", "jake", "mike", "ryan"],
        )

    def test_seed_all_is_idempotent(self):
        call_command("seed_all", stdout=StringIO())
        call_command("seed_all", stdout=StringIO())

        self.assertEqual(Photo.objects.count(), 10)
        self.assertEqual(get_user_model().objects.count(), 5)
        self.assertEqual(Like.objects.count(), 30)
        self.assertEqual(Comment.objects.count(), 13)


class GalleryViewTests(TestCase):
    def test_photo_index_requires_login(self):
        response = self.client.get(reverse("photos:index"))

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('photos:index')}")

    def test_photo_detail_requires_login(self):
        photo = self.create_photo()
        url = reverse("photos:detail", kwargs={"pk": photo.pk})

        response = self.client.get(url)

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_like_post_requires_login(self):
        photo = self.create_photo()
        url = reverse("photos:like_toggle", kwargs={"pk": photo.pk})

        response = self.client.post(url)

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_like_delete_requires_login(self):
        photo = self.create_photo()
        url = reverse("photos:like_toggle", kwargs={"pk": photo.pk})

        response = self.client.delete(url)

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_comment_create_requires_login(self):
        photo = self.create_photo()
        url = reverse("photos:comment_create", kwargs={"pk": photo.pk})

        response = self.client.post(url, {"body": "Nice frame"})

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_comment_delete_requires_login(self):
        user = self.create_user()
        comment = Comment.objects.create(user=user, photo=self.create_photo(), body="Nice frame")
        url = reverse("photos:comment_destroy", kwargs={"pk": comment.pk})

        response = self.client.delete(url)

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_photo_index_renders_ordered_gallery(self):
        user = self.create_user()
        first = self.create_photo(pexels_id=21_751_820, alt="First photo")
        second = self.create_photo(pexels_id=21_405_575, alt="Second photo")
        Like.objects.create(user=user, photo=second)
        self.client.force_login(user)

        response = self.client.get(reverse("photos:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photos/photo_list.html")
        self.assertContains(response, "All Photos")
        self.assertContains(response, f'id="photo-{first.pk}"')
        self.assertContains(response, f'id="photo-{second.pk}-like"')
        self.assertContains(response, 'x-data="photoSwipeGallery"')
        self.assertContains(response, 'data-pswp-srcset=')
        self.assertContains(response, "x-data=\"likeButton({ liked:")
        self.assertContains(response, 'hx-ext="ws"')
        self.assertContains(response, 'ws-connect="/ws/photos/')
        self.assertContains(response, '@submit="toggle()"')
        self.assertContains(response, "like_count")
        self.assertContains(response, 'class="relative aspect-square overflow-hidden rounded-2xl')
        self.assertContains(response, 'class="absolute right-3 top-3 z-10"')
        self.assertContains(response, first.photographer)
        self.assertContains(response, second.photographer)
        self.assertEqual(list(response.context["photos"]), [first, second])
        self.assertEqual(response.context["liked_photo_ids"], {second.pk})

    def test_photo_detail_renders_photo_like_button_and_source_controls(self):
        user = self.create_user()
        photo = self.create_photo()
        Like.objects.create(user=user, photo=photo)
        self.client.force_login(user)

        response = self.client.get(reverse("photos:detail", kwargs={"pk": photo.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photos/photo_detail.html")
        self.assertContains(response, photo.alt)
        self.assertContains(response, "Back to gallery")
        self.assertContains(response, "Copy source URL")
        self.assertContains(response, 'x-data="copySource"')
        self.assertContains(response, photo.url)
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, "liked: true")
        self.assertContains(response, "like_count")
        self.assertContains(response, f'hx-delete="{reverse("photos:like_toggle", kwargs={"pk": photo.pk})}"')

    def test_photo_detail_missing_photo_returns_404(self):
        self.client.force_login(self.create_user())

        response = self.client.get(reverse("photos:detail", kwargs={"pk": 99_999}))

        self.assertEqual(response.status_code, 404)

    def test_like_post_is_idempotent_and_updates_counter(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)
        url = reverse("photos:like_toggle", kwargs={"pk": photo.pk})

        first_response = self.client.post(url)
        second_response = self.client.post(url)
        photo.refresh_from_db()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertJSONEqual(first_response.content, {"liked": True, "likes_count": 1})
        self.assertEqual(Like.objects.filter(user=user, photo=photo).count(), 1)
        self.assertEqual(photo.likes_count, 1)

    def test_like_post_broadcasts_realtime_count(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)

        with patch("apps.photos.views.broadcast_photo_like_count") as broadcast:
            response = self.client.post(reverse("photos:like_toggle", kwargs={"pk": photo.pk}))

        self.assertEqual(response.status_code, 200)
        broadcast.assert_called_once()
        broadcast_photo = broadcast.call_args.args[0]
        self.assertEqual(broadcast_photo.pk, photo.pk)
        self.assertEqual(broadcast_photo.likes_count, 1)

    def test_like_post_missing_photo_returns_404(self):
        self.client.force_login(self.create_user())

        response = self.client.post(reverse("photos:like_toggle", kwargs={"pk": 99_999}))

        self.assertEqual(response.status_code, 404)

    def test_like_route_rejects_get_requests(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)

        response = self.client.get(reverse("photos:like_toggle", kwargs={"pk": photo.pk}))

        self.assertEqual(response.status_code, 405)

    def test_like_delete_is_idempotent_and_updates_counter(self):
        user = self.create_user()
        photo = self.create_photo()
        Like.objects.create(user=user, photo=photo)
        self.client.force_login(user)
        url = reverse("photos:like_toggle", kwargs={"pk": photo.pk})

        first_response = self.client.delete(url)
        second_response = self.client.delete(url)
        photo.refresh_from_db()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertJSONEqual(first_response.content, {"liked": False, "likes_count": 0})
        self.assertFalse(Like.objects.filter(user=user, photo=photo).exists())
        self.assertEqual(photo.likes_count, 0)

    def test_like_hx_request_renders_button_partial(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)

        response = self.client.post(
            reverse("photos:like_toggle", kwargs={"pk": photo.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photos/_like_button.html")
        self.assertContains(response, f'id="photo-{photo.pk}-like"')
        self.assertContains(response, "likeButton({ liked:")
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, ':aria-pressed="liked.toString()"')
        self.assertContains(response, "like_count")
        self.assertContains(response, 'data-icon="star-fill"')

    def test_like_form_fallback_redirects_to_next(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)
        url = reverse("photos:like_toggle", kwargs={"pk": photo.pk})

        response = self.client.post(url, {"next": reverse("photos:index")})
        photo.refresh_from_db()

        self.assertRedirects(response, reverse("photos:index"), fetch_redirect_response=False)
        self.assertTrue(Like.objects.filter(user=user, photo=photo).exists())
        self.assertEqual(photo.likes_count, 1)

    def test_like_form_fallback_can_unlike_with_method_override(self):
        user = self.create_user()
        photo = self.create_photo()
        Like.objects.create(user=user, photo=photo)
        self.client.force_login(user)
        url = reverse("photos:like_toggle", kwargs={"pk": photo.pk})

        response = self.client.post(url, {"_method": "delete", "next": reverse("photos:index")})
        photo.refresh_from_db()

        self.assertRedirects(response, reverse("photos:index"), fetch_redirect_response=False)
        self.assertFalse(Like.objects.filter(user=user, photo=photo).exists())
        self.assertEqual(photo.likes_count, 0)

    def test_comment_create_route_persists_comment(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)

        response = self.client.post(reverse("photos:comment_create", kwargs={"pk": photo.pk}), {"body": "  Nice frame  "})
        photo.refresh_from_db()

        self.assertRedirects(response, reverse("photos:detail", kwargs={"pk": photo.pk}), fetch_redirect_response=False)
        self.assertEqual(Comment.objects.get(photo=photo, user=user).body, "Nice frame")
        self.assertEqual(photo.comments_count, 1)

    def test_comment_create_hx_request_renders_comment_partial(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)

        response = self.client.post(
            reverse("photos:comment_create", kwargs={"pk": photo.pk}),
            {"body": "Nice frame"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "photos/_comment.html")
        self.assertContains(response, "Nice frame")

    def test_comment_create_blank_body_returns_json_errors(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)

        response = self.client.post(reverse("photos:comment_create", kwargs={"pk": photo.pk}), {"body": "   "})
        photo.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertIn("body", response.json()["errors"])
        self.assertFalse(Comment.objects.exists())
        self.assertEqual(photo.comments_count, 0)

    def test_comment_create_too_long_body_returns_json_errors(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)

        response = self.client.post(reverse("photos:comment_create", kwargs={"pk": photo.pk}), {"body": "x" * 1001})
        photo.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertIn("body", response.json()["errors"])
        self.assertFalse(Comment.objects.exists())
        self.assertEqual(photo.comments_count, 0)

    def test_comment_create_hx_invalid_body_renders_error_partial(self):
        user = self.create_user()
        photo = self.create_photo()
        self.client.force_login(user)

        response = self.client.post(
            reverse("photos:comment_create", kwargs={"pk": photo.pk}),
            {"body": "   "},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "photos/_comment_error.html")
        self.assertContains(response, "Comment body cannot be blank", status_code=400)

    def test_comment_create_missing_photo_returns_404(self):
        self.client.force_login(self.create_user())

        response = self.client.post(reverse("photos:comment_create", kwargs={"pk": 99_999}), {"body": "Nice frame"})

        self.assertEqual(response.status_code, 404)

    def test_comment_delete_route_removes_owned_comment(self):
        user = self.create_user()
        photo = self.create_photo()
        comment = Comment.objects.create(user=user, photo=photo, body="Nice frame")
        self.client.force_login(user)

        response = self.client.delete(reverse("photos:comment_destroy", kwargs={"pk": comment.pk}))
        photo.refresh_from_db()

        self.assertRedirects(response, reverse("photos:detail", kwargs={"pk": photo.pk}), fetch_redirect_response=False)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())
        self.assertEqual(photo.comments_count, 0)

    def test_comment_delete_hx_request_returns_json(self):
        user = self.create_user()
        photo = self.create_photo()
        comment = Comment.objects.create(user=user, photo=photo, body="Nice frame")
        self.client.force_login(user)

        response = self.client.delete(reverse("photos:comment_destroy", kwargs={"pk": comment.pk}), HTTP_HX_REQUEST="true")
        photo.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"deleted": True, "comment_id": comment.pk})
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())
        self.assertEqual(photo.comments_count, 0)

    def test_comment_delete_rejects_comments_owned_by_another_user(self):
        owner = self.create_user(username="brian")
        other_user = self.create_user(username="ryan")
        photo = self.create_photo()
        comment = Comment.objects.create(user=owner, photo=photo, body="Nice frame")
        self.client.force_login(other_user)

        response = self.client.delete(reverse("photos:comment_destroy", kwargs={"pk": comment.pk}))
        photo.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())
        self.assertEqual(photo.comments_count, 1)

    def test_comment_delete_missing_comment_returns_404(self):
        self.client.force_login(self.create_user())

        response = self.client.delete(reverse("photos:comment_destroy", kwargs={"pk": 99_999}))

        self.assertEqual(response.status_code, 404)

    def test_comment_delete_rejects_get_requests(self):
        user = self.create_user()
        comment = Comment.objects.create(user=user, photo=self.create_photo(), body="Nice frame")
        self.client.force_login(user)

        response = self.client.get(reverse("photos:comment_destroy", kwargs={"pk": comment.pk}))

        self.assertEqual(response.status_code, 405)

    def create_user(self, username="brian"):
        return get_user_model().objects.create_user(username=username, password="password")

    def build_photo(self, **attributes):
        defaults = {
            "pexels_id": 21_751_820,
            "width": 3888,
            "height": 5184,
            "url": "https://www.pexels.com/photo/example-21751820/",
            "photographer": "Felix",
            "photographer_url": "https://www.pexels.com/@felix",
            "photographer_id": 21_751_820,
            "avg_color": "#333831",
            "alt": "A small island surrounded by trees in the middle of a lake",
        }
        defaults.update(attributes)
        return Photo(**defaults)

    def create_photo(self, **attributes):
        photo = self.build_photo(**attributes)
        photo.save()
        return photo
