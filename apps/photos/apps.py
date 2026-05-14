from django.apps import AppConfig


class PhotosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.photos"
    label = "photos"

    def ready(self):
        import apps.photos.signals  # noqa: F401
