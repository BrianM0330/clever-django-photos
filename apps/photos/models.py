from urllib.parse import urlencode

from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models


class Photo(models.Model):
    IMAGE_BASE_OPTIONS = {"auto": "compress", "cs": "tinysrgb"}

    pexels_id = models.PositiveIntegerField(unique=True)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    url = models.URLField()
    photographer = models.CharField(max_length=255)
    photographer_url = models.URLField()
    photographer_id = models.PositiveIntegerField()
    avg_color = models.CharField(max_length=32)
    alt = models.TextField()
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "photos"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.alt

    @classmethod
    def portrait(cls):
        return cls.objects.filter(height__gt=models.F("width"))

    @classmethod
    def landscape(cls):
        return cls.objects.filter(width__gt=models.F("height"))

    @classmethod
    def square(cls):
        return cls.objects.filter(width=models.F("height"))

    @classmethod
    def by_photographer(cls, photographer_id: int):
        return cls.objects.filter(photographer_id=photographer_id)

    @property
    def src_original(self) -> str:
        return self._pexels_image_url()

    @property
    def src_large2x(self) -> str:
        return self._pexels_image_url(**self.IMAGE_BASE_OPTIONS, dpr=2, h=650, w=940)

    @property
    def src_large(self) -> str:
        return self._pexels_image_url(**self.IMAGE_BASE_OPTIONS, h=650, w=940)

    @property
    def src_medium(self) -> str:
        return self._pexels_image_url(**self.IMAGE_BASE_OPTIONS, h=350)

    @property
    def src_small(self) -> str:
        return self._pexels_image_url(**self.IMAGE_BASE_OPTIONS, h=130)

    @property
    def src_portrait(self) -> str:
        return self._pexels_image_url(**self.IMAGE_BASE_OPTIONS, fit="crop", h=1200, w=800)

    @property
    def src_landscape(self) -> str:
        return self._pexels_image_url(**self.IMAGE_BASE_OPTIONS, fit="crop", h=627, w=1200)

    @property
    def src_tiny(self) -> str:
        return self._pexels_image_url(**self.IMAGE_BASE_OPTIONS, dpr=1, fit="crop", h=200, w=280)

    @property
    def srcset(self) -> dict[str, str]:
        return {
            self.src_medium: "350w",
            self.src_large: "940w",
            self.src_large2x: "1880w",
        }

    def _pexels_image_url(self, **query) -> str:
        url = f"https://images.pexels.com/photos/{self.pexels_id}/pexels-photo-{self.pexels_id}.jpeg"
        return f"{url}?{urlencode(query)}" if query else url


class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "likes"
        constraints = [
            models.UniqueConstraint(fields=["user", "photo"], name="uniq_user_photo_like"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} likes {self.photo_id}"


class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="comments")
    body = models.TextField(validators=[MaxLengthValidator(1000)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comments"
        indexes = [
            models.Index(fields=["photo", "created_at"], name="comments_photo_created_at_idx"),
        ]

    def __str__(self) -> str:
        return self.body
