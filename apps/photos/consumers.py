from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string

from apps.photos.models import Photo
from apps.photos.realtime import photo_likes_group_name


class PhotoLikesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        self.photo_id = int(self.scope["url_route"]["kwargs"]["photo_id"])
        self.group_name = photo_likes_group_name(self.photo_id)

        likes_count = await self.get_likes_count()
        if likes_count is None:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_like_count(likes_count)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def photo_like_count(self, event):
        await self.send_like_count(event["likes_count"])

    async def send_like_count(self, likes_count):
        html = await self.render_like_count(likes_count)
        await self.send(text_data=html)

    @database_sync_to_async
    def get_likes_count(self):
        return Photo.objects.filter(pk=self.photo_id).values_list("likes_count", flat=True).first()

    @database_sync_to_async
    def render_like_count(self, likes_count):
        photo = Photo(pk=self.photo_id, likes_count=likes_count)
        return render_to_string("photos/_like_count.html", {"photo": photo, "oob": True})
