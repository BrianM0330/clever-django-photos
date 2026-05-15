from django.core.management.base import BaseCommand

from apps.analytics.jobs import update_photo_composition_scores


class Command(BaseCommand):
    help = "Analyze photos and persist composition scores."

    def add_arguments(self, parser):
        parser.add_argument("photo_ids", nargs="*", type=int)
        parser.add_argument("--only-missing", action="store_true")
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, **options):
        result = update_photo_composition_scores(
            photo_ids=options["photo_ids"] or None,
            only_missing=options["only_missing"],
            batch_size=options["batch_size"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {result['processed']} photos, updated {result['updated']}, failed {result['failed']}."
            )
        )
