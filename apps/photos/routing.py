from django.urls import re_path

from apps.photos.consumers import PhotoLikesConsumer

websocket_urlpatterns = [
    re_path(r"^ws/photos/(?P<photo_id>\d+)/likes/$", PhotoLikesConsumer.as_asgi()),
]
