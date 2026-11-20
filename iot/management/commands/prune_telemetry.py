"""Prune or wipe telemetry so the free-tier database stays small."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete old flow readings / logs (keeps users & devices). Use --wipe for all telemetry."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete ALL telemetry rows (readings, logs, consumption). Keep accounts/devices.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore prune rate limit",
        )

    def handle(self, *args, **options):
        from monitoring.retention import prune_telemetry, wipe_telemetry

        if options["wipe"]:
            result = wipe_telemetry()
            self.stdout.write(self.style.WARNING(f"Wiped telemetry: {result}"))
        else:
            result = prune_telemetry(force=True)
            self.stdout.write(self.style.SUCCESS(f"Pruned: {result}"))
