from django.core.management.base import BaseCommand

from apps.analytics.tasks import update_user_affinities


class Command(BaseCommand):
    help = "Compute and persist user affinity scores from likes."

    def add_arguments(self, parser):
        parser.add_argument("--min-overlap", type=int, default=3)
        parser.add_argument("--threshold", type=float, default=0.4)

    def handle(self, *args, **options):
        result = update_user_affinities(
            min_overlap=options["min_overlap"],
            threshold=options["threshold"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {result['pairs_written']} affinity rows with threshold={result['threshold']} min_overlap={result['min_overlap']}."
            )
        )
