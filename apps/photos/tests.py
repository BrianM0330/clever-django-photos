from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.photos.models import Comment, Like, Photo


class GalleryModelTests(TestCase):
    def test_unique_user_photo_like_constraint_enforced(self):
        user = self.create_user()
        photo = self.create_photo()
        Like.objects.create(user=user, photo=photo)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Like.objects.create(user=user, photo=photo)

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
