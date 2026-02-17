from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import role_required
from apps.budget.models import Expense

from .forms import ActivityForm, ProjectForm
from .models import Activity, FiscalYear, Project
from .utils import get_projects_for_user


@login_required
def project_list(request):
    projects = get_projects_for_user(request.user)

    # Filters
    fiscal_year = request.GET.get('fiscal_year')
    status = request.GET.get('status')
    search = request.GET.get('search')

    if fiscal_year:
        projects = projects.filter(fiscal_year_id=fiscal_year)
    if status:
        projects = projects.filter(status=status)
    if search:
        projects = projects.filter(
            Q(name__icontains=search) | Q(project_code__icontains=search)
        )

    fiscal_years = FiscalYear.objects.all()

    context = {
        'projects': projects,
        'fiscal_years': fiscal_years,
        'status_choices': Project.STATUS_CHOICES,
        'current_fiscal_year': fiscal_year,
        'current_status': status,
        'current_search': search or '',
    }
    return render(request, 'projects/project_list.html', context)


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=pk).exists():
        raise PermissionDenied

    activities = project.activities.all()
    recent_expenses = Expense.objects.filter(
        activity__project=project
    ).select_related('activity', 'created_by').order_by('-created_at')[:10]

    context = {
        'project': project,
        'activities': activities,
        'recent_expenses': recent_expenses,
    }
    return render(request, 'projects/project_detail.html', context)


@role_required(['planner', 'head', 'admin'])
def project_create(request):
    profile = getattr(request.user, 'profile', None)

    if request.method == 'POST':
        form = ProjectForm(request.POST, user=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            if profile and profile.department:
                project.department = profile.department
            project.save()
            form.save_m2m()
            messages.success(request, f'สร้างโครงการ "{project.name}" สำเร็จ')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm(user=request.user)

    return render(request, 'projects/project_form.html', {
        'form': form,
        'title': 'สร้างโครงการใหม่',
        'user_profile': profile,
    })


@role_required(['planner', 'head', 'admin'])
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=pk).exists():
        raise PermissionDenied

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'แก้ไขโครงการ "{project.name}" สำเร็จ')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project, user=request.user)

    return render(request, 'projects/project_form.html', {
        'form': form,
        'project': project,
        'title': f'แก้ไขโครงการ: {project.name}',
        'user_profile': getattr(request.user, 'profile', None),
    })


@role_required(['planner', 'head', 'admin'])
def project_status_change(request, pk):
    if request.method != 'POST':
        raise PermissionDenied

    project = get_object_or_404(Project, pk=pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=pk).exists():
        raise PermissionDenied

    new_status = request.POST.get('status')
    valid_statuses = [s[0] for s in Project.STATUS_CHOICES]
    if new_status not in valid_statuses:
        messages.error(request, 'สถานะไม่ถูกต้อง')
        return redirect('projects:project_detail', pk=pk)

    project.status = new_status
    project.save()
    messages.success(request, f'เปลี่ยนสถานะโครงการเป็น "{project.get_status_display()}" สำเร็จ')
    return redirect('projects:project_detail', pk=pk)


@login_required
def activity_detail(request, project_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=project_pk).exists():
        raise PermissionDenied

    activity = get_object_or_404(Activity, pk=pk, project=project)
    expenses = Expense.objects.filter(activity=activity).select_related(
        'created_by', 'approved_by'
    )

    context = {
        'project': project,
        'activity': activity,
        'expenses': expenses,
    }
    return render(request, 'projects/activity_detail.html', context)


@role_required(['planner', 'head', 'admin'])
def activity_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=project_pk).exists():
        raise PermissionDenied

    if request.method == 'POST':
        form = ActivityForm(request.POST, project=project, user=request.user)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.project = project
            # Auto-increment activity_number
            max_num = project.activities.order_by('-activity_number').values_list(
                'activity_number', flat=True
            ).first() or 0
            activity.activity_number = max_num + 1
            activity.save()
            form.save_m2m()
            messages.success(request, f'เพิ่มกิจกรรม "{activity.name}" สำเร็จ')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ActivityForm(project=project, user=request.user)

    return render(request, 'projects/activity_form.html', {
        'form': form,
        'project': project,
        'title': 'เพิ่มกิจกรรมใหม่',
    })


@role_required(['planner', 'head', 'admin'])
def activity_edit(request, project_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=project_pk).exists():
        raise PermissionDenied

    activity = get_object_or_404(Activity, pk=pk, project=project)

    if request.method == 'POST':
        form = ActivityForm(request.POST, instance=activity, project=project, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'แก้ไขกิจกรรม "{activity.name}" สำเร็จ')
            return redirect('projects:activity_detail', project_pk=project.pk, pk=activity.pk)
    else:
        form = ActivityForm(instance=activity, project=project, user=request.user)

    return render(request, 'projects/activity_form.html', {
        'form': form,
        'project': project,
        'activity': activity,
        'title': f'แก้ไขกิจกรรม: {activity.name}',
    })
