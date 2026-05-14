import csv
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.photos.models import Comment, Like, Photo


SEED_USERNAMES = ["brian", "ryan", "jake", "mike", "admin"]
COMMENT_BODIES = [
    "The color palette on this one is excellent.",
    "This would look great as a hero image.",
    "Love the composition here.",
    "The lighting makes this feel really calm.",
    "Strong candidate for the gallery grid.",
    "The crop options should work well for this photo.",
    "This one has a nice sense of depth.",
]
PHOTO_CSV_PATH = Path(settings.BASE_DIR) / "data" / "seeds" / "photos.csv"


@dataclass
class SeedSummary:
    photos: int = 0
    users: int = 0
    likes_created: int = 0
    comments_created: int = 0


class Command(BaseCommand):
    help = "Seed photos, users, likes, and comments from the Rails reference data."

    def handle(self, *args, **options):
        if not PHOTO_CSV_PATH.exists():
            raise CommandError(f"CSV file not found: {PHOTO_CSV_PATH}")

        with transaction.atomic():
            summary = SeedSummary()
            summary.photos = self._seed_photos()
            users = self._seed_users()
            summary.users = len(users)
            summary.likes_created, summary.comments_created = self._seed_social(users)

        self.stdout.write(f"Seeded {summary.photos} photos from {PHOTO_CSV_PATH.name}.")
        self.stdout.write("Seeded Clever users.")
        self.stdout.write(
            f"Seeded {summary.likes_created} new likes and {summary.comments_created} new comments."
        )

    def _seed_photos(self) -> int:
        seeded_count = 0

        try:
            with PHOTO_CSV_PATH.open(newline="") as csv_file:
                for row in csv.DictReader(csv_file):
                    Photo.objects.update_or_create(
                        pexels_id=self._required_int(row, "id"),
                        defaults={
                            "width": self._required_int(row, "width"),
                            "height": self._required_int(row, "height"),
                            "url": self._required_value(row, "url"),
                            "photographer": self._required_value(row, "photographer"),
                            "photographer_url": self._required_value(row, "photographer_url"),
                            "photographer_id": self._required_int(row, "photographer_id"),
                            "avg_color": self._required_value(row, "avg_color"),
                            "alt": self._required_value(row, "alt"),
                        },
                    )
                    seeded_count += 1
        except csv.Error as error:
            raise CommandError(f"Malformed CSV in {PHOTO_CSV_PATH}: {error}") from error

        return seeded_count

    def _seed_users(self):
        User = get_user_model()

        for username in SEED_USERNAMES:
            user, _created = User.objects.update_or_create(username=username, defaults={})
            user.set_password("password")
            user.save(update_fields=["password"])

        return list(User.objects.filter(username__in=SEED_USERNAMES).order_by("username"))

    def _seed_social(self, users) -> tuple[int, int]:
        photos = list(Photo.objects.order_by("pexels_id"))
        if not users or not photos:
            self.stderr.write("======== WARNING: Skipped social seeds because photos or users are missing. ========")
            return 0, 0

        likes_created = 0
        comments_created = 0

        for photo_index, photo in enumerate(photos):
            liker_count = (photo_index % len(users)) + 1
            for user in users[:liker_count]:
                _like, created = Like.objects.get_or_create(user=user, photo=photo)
                likes_created += int(created)

        for photo_index, photo in enumerate(photos):
            comment_count = photo_index % 4
            for comment_index in range(comment_count):
                user = users[(photo_index + comment_index) % len(users)]
                body = COMMENT_BODIES[(photo_index + comment_index) % len(COMMENT_BODIES)]
                _comment, created = Comment.objects.get_or_create(user=user, photo=photo, body=body)
                comments_created += int(created)

        return likes_created, comments_created

    def _required_value(self, row: dict[str, str], header: str) -> str:
        value = row.get(header, "").strip()
        if not value:
            raise CommandError(f"missing required CSV field: {header}")
        return value

    def _required_int(self, row: dict[str, str], header: str) -> int:
        value = self._required_value(row, header)
        try:
            return int(value)
        except ValueError as error:
            raise CommandError(f"invalid integer for CSV field {header}: {value}") from error
