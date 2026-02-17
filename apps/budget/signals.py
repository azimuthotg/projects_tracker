from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Expense


@receiver(post_save, sender=Expense)
def check_budget_threshold(sender, instance, **kwargs):
    """When expense is approved, check if budget usage exceeds threshold."""
    if instance.status != 'approved':
        return

    activity = instance.activity
    usage_percent = activity.budget_usage_percent

    # Send notification to each person in notify_persons
    for person in activity.notify_persons.all():
        if not hasattr(person, 'profile'):
            continue

        profile = person.profile
        if not profile.notify_budget_alert:
            continue

        if usage_percent >= profile.budget_threshold:
            # Will be implemented in notifications phase
            pass
