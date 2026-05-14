from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.projects.models import Activity, Project
from apps.projects.utils import get_viewable_projects


def _check_planner_role(user):
    role = getattr(getattr(user, 'profile', None), 'role', 'staff')
    if role not in ('planner', 'head', 'admin'):
        raise PermissionDenied


@login_required
@require_POST
def send_project_notify(request, pk):
    _check_planner_role(request.user)
    project = get_object_or_404(Project, pk=pk)
    if not get_viewable_projects(request.user).filter(pk=pk).exists():
        raise PermissionDenied

    message = request.POST.get('message', '').strip()
    if not message:
        messages.error(request, 'กรุณากรอกข้อความแจ้งเตือน')
        return redirect('projects:project_detail', pk=pk)

    from apps.notifications.services import LINEService
    service = LINEService()
    sent = failed = no_line = 0

    for person in project.notify_persons.all():
        profile = getattr(person, 'profile', None)
        if not profile or not profile.line_user_id:
            no_line += 1
            continue
        if service.send_manual_notify(person, message, project=project):
            sent += 1
        else:
            failed += 1

    if sent:
        messages.success(request, f'ส่งแจ้งเตือน LINE สำเร็จ {sent} คน')
    if failed:
        messages.warning(request, f'ส่งไม่สำเร็จ {failed} คน')
    if no_line and not sent and not failed:
        messages.info(request, 'ไม่มีผู้รับที่เชื่อมต่อ LINE ไว้')

    return redirect('projects:project_detail', pk=pk)


@login_required
@require_POST
def send_activity_notify(request, project_pk, pk):
    _check_planner_role(request.user)
    project = get_object_or_404(Project, pk=project_pk)
    if not get_viewable_projects(request.user).filter(pk=project_pk).exists():
        raise PermissionDenied
    activity = get_object_or_404(Activity, pk=pk, project=project)

    message = request.POST.get('message', '').strip()
    if not message:
        messages.error(request, 'กรุณากรอกข้อความแจ้งเตือน')
        return redirect('projects:activity_detail', project_pk=project_pk, pk=pk)

    from apps.notifications.services import LINEService
    service = LINEService()
    sent = failed = no_line = 0

    for person in activity.notify_persons.all():
        profile = getattr(person, 'profile', None)
        if not profile or not profile.line_user_id:
            no_line += 1
            continue
        if service.send_manual_notify(person, message, project=project, activity=activity):
            sent += 1
        else:
            failed += 1

    if sent:
        messages.success(request, f'ส่งแจ้งเตือน LINE สำเร็จ {sent} คน')
    if failed:
        messages.warning(request, f'ส่งไม่สำเร็จ {failed} คน')
    if no_line and not sent and not failed:
        messages.info(request, 'ไม่มีผู้รับที่เชื่อมต่อ LINE ไว้')

    return redirect('projects:activity_detail', project_pk=project_pk, pk=pk)
