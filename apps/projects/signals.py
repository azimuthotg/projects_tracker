from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


@receiver([post_save, post_delete], sender='projects.ProjectBudgetSource')
def update_project_total_budget(sender, instance, **kwargs):
    """Recalculate project.total_budget whenever a budget source is saved or deleted."""
    from .models import Project
    total = instance.project.budget_sources.aggregate(total=Sum('amount'))['total'] or 0
    Project.objects.filter(pk=instance.project_id).update(total_budget=total)


@receiver(post_save, sender='projects.Activity')
def sync_project_status_from_activity(sender, instance, **kwargs):
    """Auto-update project status whenever an activity status changes.

    Rules (skip if project is draft/cancelled — manual-only):
      all completed               → project = completed
      any in_progress             → project = active
      some completed + rest pending → project = active (work underway)
      all pending                 → project = not_started
    """
    from .models import Project
    project = instance.project

    # Never auto-override these — require explicit human decision
    if project.status in ('draft', 'cancelled'):
        return

    activities = project.activities.exclude(status='cancelled')
    if not activities.exists():
        return

    statuses = list(activities.values_list('status', flat=True))

    if all(s == 'completed' for s in statuses):
        new_status = 'completed'
    elif any(s in ('in_progress', 'completed') for s in statuses):
        new_status = 'active'
    else:
        # all pending
        new_status = 'not_started'

    if project.status != new_status:
        Project.objects.filter(pk=project.pk).update(status=new_status)
