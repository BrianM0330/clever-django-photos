from django.urls import re_path

from apps.photos.consumers import PhotoLikesConsumer

websocket_urlpatterns = [
    # Compatibility for already-rendered pages from the previous per-photo socket implementation.
    # New pages use the global `/ws/photos/likes/` stream from `base.html`.
    re_path(r"^ws/photos/\d+/likes/$", PhotoLikesConsumer.as_asgi()),
    re_path(r"^ws/photos/likes/$", PhotoLikesConsumer.as_asgi()),
]
