from urllib.error import HTTPError, URLError

from django.db import transaction
from django.tasks import task

from apps.analytics.models import UserAffinity
from apps.analytics.services import compute_jaccard_affinities, detect_mood, score_rule_of_thirds
from apps.photos.models import Like, Photo

IMAGE_ANALYSIS_EXCEPTIONS = (HTTPError, URLError, OSError, ValueError)


def _photo_queryset(*, photo_ids=None):
    queryset = Photo.objects.order_by("id")
    if photo_ids:
        queryset = queryset.filter(id__in=photo_ids)
    return queryset


def _update_photo_field(*, photo_ids=None, batch_size: int = 100, field_name: str, compute_value, only_missing: bool = False):
    queryset = _photo_queryset(photo_ids=photo_ids)
    if only_missing:
        queryset = queryset.filter(**{f"{field_name}__isnull": True})

    pending_updates = []
    processed = 0
    updated = 0
    failed = 0

    for photo in queryset.iterator(chunk_size=batch_size):
        processed += 1

        try:
            value = compute_value(photo.src_large)
        except IMAGE_ANALYSIS_EXCEPTIONS:
            failed += 1
            continue

        if getattr(photo, field_name) == value:
            continue

        setattr(photo, field_name, value)
        pending_updates.append(photo)
        updated += 1

        if len(pending_updates) >= batch_size:
            Photo.objects.bulk_update(pending_updates, [field_name])
            pending_updates.clear()

    if pending_updates:
        Photo.objects.bulk_update(pending_updates, [field_name])

    return {
        "processed": processed,
        "updated": updated,
        "failed": failed,
        "field": field_name,
    }


@task()
def update_user_affinities(*, min_overlap: int = 3, threshold: float = 0.4):
    affinity_rows = compute_jaccard_affinities(
        Like.objects.values("user_id", "photo_id"),
        min_overlap=min_overlap,
        threshold=threshold,
    )

    with transaction.atomic():
        UserAffinity.objects.all().delete()
        UserAffinity.objects.bulk_create(
            [
                UserAffinity(user_id=user_id, affinity_user_id=affinity_user_id, score=score)
                for user_id, affinity_user_id, score in affinity_rows
            ],
            batch_size=500,
        )

    return {
        "pairs_written": len(affinity_rows),
        "threshold": threshold,
        "min_overlap": min_overlap,
    }


@task()
def update_photo_moods(*, photo_ids=None, only_missing: bool = False, batch_size: int = 100):
    return _update_photo_field(
        photo_ids=photo_ids,
        batch_size=batch_size,
        field_name="mood",
        compute_value=detect_mood,
        only_missing=only_missing,
    )


@task()
def update_photo_composition_scores(*, photo_ids=None, only_missing: bool = False, batch_size: int = 100):
    return _update_photo_field(
        photo_ids=photo_ids,
        batch_size=batch_size,
        field_name="composition_score",
        compute_value=score_rule_of_thirds,
        only_missing=only_missing,
    )
