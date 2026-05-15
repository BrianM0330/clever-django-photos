from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from django.urls import reverse

from apps.photos.models import Photo
from apps.photos.realtime import PHOTO_LIKES_GROUP_NAME


class PhotoLikesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        self.group_name = PHOTO_LIKES_GROUP_NAME

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def photo_like_count(self, event):
        show_toast = event.get("liked_by_user_id") != self.scope["user"].pk
        await self.send_like_count(
            event["likes_count"],
            photo_id=event["photo_id"],
            liked_by_username=event.get("liked_by_username") if show_toast else None,
        )

    async def send_like_count(self, likes_count, *, photo_id, liked_by_username=None):
        html = self.render_like_count(photo_id, likes_count, liked_by_username=liked_by_username)
        await self.send(text_data=html)

    def render_like_count(self, photo_id, likes_count, *, liked_by_username=None):
        photo = Photo(pk=photo_id, likes_count=likes_count)
        html = render_to_string("photos/_like_count.html", {"photo": photo, "oob": True})
        if liked_by_username:
            html += render_to_string(
                "partials/_toast.html",
                {
                    "message": f"{liked_by_username} liked a pic!",
                    "url": reverse("photos:detail", kwargs={"pk": photo_id}),
                },
            )
        return html
