from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.photos.models import Comment, Like, Photo


# django doesnt have the convenience of rails with counter_cache. This is how I'm handling it. I miss rails!
@receiver(post_save, sender=Like)
def increment_photo_likes_count(sender, instance, created, **kwargs):
    if created:
        Photo.objects.filter(pk=instance.photo_id).update(
            likes_count=F("likes_count") + 1)


@receiver(post_delete, sender=Like)
def decrement_photo_likes_count(sender, instance, **kwargs):
    Photo.objects.filter(pk=instance.photo_id, likes_count__gt=0).update(
        likes_count=F("likes_count") - 1)


@receiver(post_save, sender=Comment)
def increment_photo_comments_count(sender, instance, created, **kwargs):
    if created:
        Photo.objects.filter(pk=instance.photo_id).update(
            comments_count=F("comments_count") + 1)


@receiver(post_delete, sender=Comment)
def decrement_photo_comments_count(sender, instance, **kwargs):
    Photo.objects.filter(pk=instance.photo_id, comments_count__gt=0).update(
        comments_count=F("comments_count") - 1)
