from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


PHOTO_LIKES_GROUP_NAME = "photo_likes"


def broadcast_photo_like_count(photo, *, liked_by=None) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    event = {
        "type": "photo.like_count",
        "photo_id": photo.pk,
        "likes_count": photo.likes_count,
    }
    if liked_by is not None:
        event["liked_by_user_id"] = liked_by.pk
        event["liked_by_username"] = liked_by.username

    async_to_sync(channel_layer.group_send)(PHOTO_LIKES_GROUP_NAME, event)
