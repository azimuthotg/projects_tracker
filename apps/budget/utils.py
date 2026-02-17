from .models import Expense


def get_expenses_for_user(user):
    """Return expenses queryset filtered by user's role."""
    if not hasattr(user, 'profile'):
        return Expense.objects.none()

    role = user.profile.role

    if role == 'admin':
        return Expense.objects.all()
    elif role in ('planner', 'head'):
        return Expense.objects.filter(
            activity__project__department=user.profile.department
        )
    else:
        return Expense.objects.filter(created_by=user)
