from .models import ProjectDeleteRequest


def pending_delete_requests(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        if request.user.profile.role == 'admin':
            count = ProjectDeleteRequest.objects.filter(status='pending').count()
            return {'pending_delete_requests_count': count}
    return {'pending_delete_requests_count': 0}
