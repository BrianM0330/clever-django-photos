from django.tasks import task

from apps.analytics import jobs


@task()
def update_user_affinities(*, min_overlap: int = 3, threshold: float = 0.4):
    return jobs.update_user_affinities(min_overlap=min_overlap, threshold=threshold)


@task()
def update_photo_moods(*, photo_ids=None, only_missing: bool = False, batch_size: int = 100):
    return jobs.update_photo_moods(photo_ids=photo_ids, only_missing=only_missing, batch_size=batch_size)


@task()
def update_photo_composition_scores(*, photo_ids=None, only_missing: bool = False, batch_size: int = 100):
    return jobs.update_photo_composition_scores(photo_ids=photo_ids, only_missing=only_missing, batch_size=batch_size)
