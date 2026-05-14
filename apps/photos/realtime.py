from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def photo_likes_group_name(photo_id: int) -> str:
    return f"photo_{photo_id}_likes"


def broadcast_photo_like_count(photo) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        photo_likes_group_name(photo.pk),
        {
            "type": "photo.like_count",
            "photo_id": photo.pk,
            "likes_count": photo.likes_count,
        },
    )
