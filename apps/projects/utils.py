from django.db.models import Q

from .models import Project


def get_viewable_projects(user):
    """Projects the user can VIEW. Staff sees all projects in their department."""
    if not hasattr(user, 'profile'):
        return Project.objects.none()
    role = user.profile.role
    if role == 'admin':
        return Project.objects.all()
    if role in ('planner', 'head', 'staff'):
        return Project.objects.filter(department=user.profile.department)
    if role == 'executive':
        return Project.objects.all()
    return Project.objects.none()


def get_actionable_projects(user):
    """Projects the user can MODIFY. Staff limited to projects they are responsible/notify for."""
    if not hasattr(user, 'profile'):
        return Project.objects.none()
    role = user.profile.role
    if role == 'admin':
        return Project.objects.all()
    if role in ('planner', 'head'):
        return Project.objects.filter(department=user.profile.department)
    # staff
    return Project.objects.filter(
        Q(responsible_persons=user) | Q(notify_persons=user)
    ).distinct()


def get_projects_for_user(user):
    """Alias kept for backward compatibility — returns actionable projects."""
    return get_actionable_projects(user)
