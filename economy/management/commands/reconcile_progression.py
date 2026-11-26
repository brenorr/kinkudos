from django.core.management.base import BaseCommand

from economy.progression import reconcile_unlocks


class Command(BaseCommand):
    help = "Grant eligible progression unlocks without sending notifications."

    def handle(self, *args, **options):
        reconcile_unlocks()
        self.stdout.write(self.style.SUCCESS("Progression unlocks reconciled."))
