from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Expense


@receiver(post_save, sender=Expense)
def check_budget_threshold(sender, instance, **kwargs):
    """When expense is approved/rejected, send LINE notifications."""
    if instance.status not in ('approved', 'rejected'):
        return

    from apps.notifications.services import LINEService
    service = LINEService()

    activity = instance.activity

    if instance.status == 'approved':
        usage_percent = activity.budget_usage_percent

        # Budget alert → notify_persons who have LINE + notify_budget_alert on
        for person in activity.notify_persons.all():
            if not hasattr(person, 'profile'):
                continue
            profile = person.profile
            if not profile.line_user_id:
                continue
            if not profile.notify_budget_alert:
                continue
            if usage_percent >= profile.budget_threshold:
                try:
                    service.send_budget_alert(person, activity, usage_percent)
                except Exception:
                    pass

    # Expense notification → notify creator
    creator = instance.created_by
    if creator and hasattr(creator, 'profile') and creator.profile.line_user_id:
        try:
            service.send_expense_notification(creator, instance, instance.status)
        except Exception:
            pass
