from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


@receiver([post_save, post_delete], sender='projects.ProjectBudgetSource')
def update_project_total_budget(sender, instance, **kwargs):
    """Recalculate project.total_budget whenever a budget source is saved or deleted."""
    from .models import Project
    total = instance.project.budget_sources.aggregate(total=Sum('amount'))['total'] or 0
    Project.objects.filter(pk=instance.project_id).update(total_budget=total)
