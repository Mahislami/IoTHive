from django.core.management.base import BaseCommand

from devices.recommendations import generate_recommendations


class Command(BaseCommand):
    help = "Generate or refresh device recommendations."

    def handle(self, *args, **options):
        recs = generate_recommendations()
        self.stdout.write(self.style.SUCCESS(f"Refreshed {len(recs)} recommendations."))
