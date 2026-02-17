from django.apps import AppConfig


class BudgetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.budget'
    verbose_name = 'งบประมาณ'

    def ready(self):
        import apps.budget.signals  # noqa: F401
