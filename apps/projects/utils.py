from .models import Project


def get_projects_for_user(user):
    """Return projects queryset filtered by user's role."""
    if not hasattr(user, 'profile'):
        return Project.objects.none()

    role = user.profile.role

    if role == 'admin':
        return Project.objects.all()
    elif role in ('planner', 'head'):
        return Project.objects.filter(department=user.profile.department)
    else:
        return Project.objects.filter(responsible_persons=user).distinct()
