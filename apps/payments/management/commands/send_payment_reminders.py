from django.core.management.base import BaseCommand

from apps.payments.services import send_payment_reminders


class Command(BaseCommand):
    help = "Queue configured in-app reminders for pending offline payments."

    def handle(self, *args, **options):
        queued = send_payment_reminders()
        self.stdout.write(
            self.style.SUCCESS(f"Queued {queued} payment reminder(s).")
        )
