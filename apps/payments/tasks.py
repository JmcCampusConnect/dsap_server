try:
    from celery import shared_task
except ImportError:
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from apps.payments.services import send_payment_reminders


@shared_task(name="send_payment_reminders")
def send_payment_reminders_task():
    """
    Daily Celery Beat task to queue payment reminders for pending offline payments.
    """
    return send_payment_reminders()

