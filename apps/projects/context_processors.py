from .models import ProjectDeleteRequest


def pending_delete_requests(request):
    ctx = {'pending_delete_requests_count': 0, 'pending_expenses_count': 0}
    if not request.user.is_authenticated or not hasattr(request.user, 'profile'):
        return ctx
    role = request.user.profile.role
    if role == 'admin':
        ctx['pending_delete_requests_count'] = ProjectDeleteRequest.objects.filter(status='pending').count()
    if role in ('head', 'admin'):
        from apps.budget.utils import get_expenses_for_user
        ctx['pending_expenses_count'] = get_expenses_for_user(request.user).filter(status='pending').count()
    return ctx
