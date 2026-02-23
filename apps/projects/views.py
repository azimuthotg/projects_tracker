from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.audit import get_client_ip, log_action
from apps.accounts.decorators import role_required
from apps.budget.forms import BudgetTransferForm
from apps.budget.models import BudgetTransfer, Expense

from .forms import ActivityForm, ActivityReportForm, ProjectBudgetSourceFormSet, ProjectForm
from .models import Activity, ActivityReport, FiscalYear, Project, ProjectDeleteRequest
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
        form = ProjectForm(request.POST, request.FILES, user=request.user)
        budget_formset = ProjectBudgetSourceFormSet(request.POST)
        if form.is_valid() and budget_formset.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.total_budget = 0  # will be updated by signal after budget sources saved
            if 'department' not in form.fields and profile and profile.department:
                project.department = profile.department
            project.save()
            form.save_m2m()
            budget_formset.instance = project
            budget_formset.save()
            log_action(
                actor=request.user, action='PROJECT_CREATE',
                target_repr=f'{project.project_code} - {project.name}',
                ip_address=get_client_ip(request),
            )
            messages.success(request, f'สร้างโครงการ "{project.name}" สำเร็จ')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm(user=request.user)
        budget_formset = ProjectBudgetSourceFormSet()

    from .forms import _apply_tailwind_formset
    _apply_tailwind_formset(budget_formset)
    return render(request, 'projects/project_form.html', {
        'form': form,
        'budget_formset': budget_formset,
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
        form = ProjectForm(request.POST, request.FILES, instance=project, user=request.user)
        budget_formset = ProjectBudgetSourceFormSet(request.POST, instance=project)
        if form.is_valid() and budget_formset.is_valid():
            form.save()
            budget_formset.save()
            log_action(
                actor=request.user, action='PROJECT_UPDATE',
                target_repr=f'{project.project_code} - {project.name}',
                ip_address=get_client_ip(request),
            )
            messages.success(request, f'แก้ไขโครงการ "{project.name}" สำเร็จ')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project, user=request.user)
        budget_formset = ProjectBudgetSourceFormSet(instance=project)

    from .forms import _apply_tailwind_formset
    _apply_tailwind_formset(budget_formset)
    return render(request, 'projects/project_form.html', {
        'form': form,
        'budget_formset': budget_formset,
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

    old_status = project.status
    project.status = new_status
    project.save()
    log_action(
        actor=request.user, action='PROJECT_STATUS',
        target_repr=f'{project.project_code} - {project.name}',
        detail=f'สถานะ: {old_status} → {new_status}',
        ip_address=get_client_ip(request),
    )
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
        'created_by', 'approved_by', 'activity_report'
    )
    reports = ActivityReport.objects.filter(activity=activity).select_related('created_by')

    context = {
        'project': project,
        'activity': activity,
        'expenses': expenses,
        'reports': reports,
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
            log_action(
                actor=request.user, action='ACTIVITY_CREATE',
                target_repr=f'{project.project_code} / กิจกรรม {activity.activity_number}: {activity.name}',
                ip_address=get_client_ip(request),
            )
            messages.success(request, f'เพิ่มกิจกรรม "{activity.name}" สำเร็จ')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ActivityForm(project=project, user=request.user)

    return render(request, 'projects/activity_form.html', {
        'form': form,
        'project': project,
        'project_sources': project.budget_source_summary(),
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
            log_action(
                actor=request.user, action='ACTIVITY_UPDATE',
                target_repr=f'{project.project_code} / กิจกรรม {activity.activity_number}: {activity.name}',
                ip_address=get_client_ip(request),
            )
            messages.success(request, f'แก้ไขกิจกรรม "{activity.name}" สำเร็จ')
            return redirect('projects:activity_detail', project_pk=project.pk, pk=activity.pk)
    else:
        form = ActivityForm(instance=activity, project=project, user=request.user)

    return render(request, 'projects/activity_form.html', {
        'form': form,
        'project': project,
        'activity': activity,
        'project_sources': project.budget_source_summary(exclude_activity_pk=activity.pk),
        'title': f'แก้ไขกิจกรรม: {activity.name}',
    })


@role_required(['planner', 'head', 'admin'])
def project_delete_request(request, pk):
    project = get_object_or_404(Project, pk=pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=pk).exists():
        raise PermissionDenied

    # admin ลบตรงได้เลยโดยไม่ต้องขออนุมัติ
    if request.user.profile.role == 'admin':
        if request.method == 'POST':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                messages.error(request, 'กรุณาระบุเหตุผลการลบ')
                return render(request, 'projects/project_delete_request.html', {'project': project})
            # บันทึก audit log ก่อนลบ
            ProjectDeleteRequest.objects.create(
                project=project,
                requested_by=request.user,
                reason=reason,
                status='approved',
                reviewed_by=request.user,
                reviewed_at=timezone.now(),
                review_remark='ลบโดย admin โดยตรง',
            )
            project_name = project.name
            project_code = project.project_code
            log_action(
                actor=request.user, action='PROJECT_DELETE',
                target_repr=f'{project_code} - {project_name}',
                detail=f'เหตุผล: {reason}',
                ip_address=get_client_ip(request),
            )
            project.delete()
            messages.success(request, f'ลบโครงการ "{project_name}" สำเร็จ')
            return redirect('projects:project_list')
        return render(request, 'projects/project_delete_request.html', {
            'project': project,
            'is_admin': True,
        })

    # planner/head ส่งคำขอรอ admin อนุมัติ
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'กรุณาระบุเหตุผลการลบ')
            return render(request, 'projects/project_delete_request.html', {'project': project})
        with transaction.atomic():
            locked_project = Project.objects.select_for_update().get(pk=pk)
            if locked_project.delete_requests.filter(status='pending').exists():
                messages.warning(request, 'มีคำขอลบโครงการนี้รอการพิจารณาอยู่แล้ว')
                return redirect('projects:project_detail', pk=pk)
            ProjectDeleteRequest.objects.create(
                project=locked_project,
                requested_by=request.user,
                reason=reason,
            )
        log_action(
            actor=request.user, action='PROJECT_DELETE_REQUEST',
            target_repr=f'{project.project_code} - {project.name}',
            detail=f'เหตุผล: {reason}',
            ip_address=get_client_ip(request),
        )
        messages.success(request, f'ส่งคำขอลบโครงการ "{project.name}" แล้ว รอ admin อนุมัติ')
        return redirect('projects:project_detail', pk=pk)

    pending = project.delete_requests.filter(status='pending').exists()
    if pending:
        messages.warning(request, 'มีคำขอลบโครงการนี้รอการพิจารณาอยู่แล้ว')
        return redirect('projects:project_detail', pk=pk)

    return render(request, 'projects/project_delete_request.html', {
        'project': project,
        'is_admin': False,
    })


@role_required(['admin'])
def delete_request_list(request):
    pending = ProjectDeleteRequest.objects.filter(status='pending').select_related(
        'project', 'requested_by'
    )
    history = ProjectDeleteRequest.objects.exclude(status='pending').select_related(
        'project', 'requested_by', 'reviewed_by'
    )[:50]
    return render(request, 'projects/delete_request_list.html', {
        'pending': pending,
        'history': history,
    })


@login_required
def activity_report_create(request, activity_pk):
    activity = get_object_or_404(Activity, pk=activity_pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=activity.project_id).exists():
        raise PermissionDenied

    if request.method == 'POST':
        form = ActivityReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.activity = activity
            report.created_by = request.user
            last = ActivityReport.objects.filter(activity=activity).aggregate(
                max_round=models.Max('round_number')
            )['max_round'] or 0
            report.round_number = last + 1
            report.save()
            messages.success(request, f'บันทึกรายงานครั้งที่ {report.round_number} สำเร็จ')
            return redirect('projects:activity_detail',
                            project_pk=activity.project_id, pk=activity.pk)
    else:
        form = ActivityReportForm()

    return render(request, 'projects/activity_report_form.html', {
        'form': form,
        'activity': activity,
        'project': activity.project,
        'title': 'บันทึกรายงานกิจกรรมย่อย',
    })


@login_required
def activity_report_edit(request, pk):
    report = get_object_or_404(ActivityReport, pk=pk)
    activity = report.activity
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=activity.project_id).exists():
        raise PermissionDenied

    if request.method == 'POST':
        form = ActivityReportForm(request.POST, request.FILES, instance=report)
        if form.is_valid():
            form.save()
            messages.success(request, f'แก้ไขรายงานครั้งที่ {report.round_number} สำเร็จ')
            return redirect('projects:activity_detail',
                            project_pk=activity.project_id, pk=activity.pk)
    else:
        form = ActivityReportForm(instance=report)

    return render(request, 'projects/activity_report_form.html', {
        'form': form,
        'report': report,
        'activity': activity,
        'project': activity.project,
        'title': f'แก้ไขรายงานครั้งที่ {report.round_number}',
    })


@login_required
def activity_report_delete(request, pk):
    report = get_object_or_404(ActivityReport, pk=pk)
    activity = report.activity
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=activity.project_id).exists():
        raise PermissionDenied

    if request.method == 'POST':
        round_number = report.round_number
        report.delete()
        messages.success(request, f'ลบรายงานครั้งที่ {round_number} สำเร็จ')
        return redirect('projects:activity_detail',
                        project_pk=activity.project_id, pk=activity.pk)

    return render(request, 'projects/activity_report_confirm_delete.html', {
        'report': report,
        'activity': activity,
        'project': activity.project,
    })


@role_required(['admin'])
def delete_request_review(request, pk):
    delete_req = get_object_or_404(ProjectDeleteRequest, pk=pk, status='pending')

    if request.method == 'POST':
        action = request.POST.get('action')
        remark = request.POST.get('remark', '').strip()

        if action not in ('approve', 'reject'):
            messages.error(request, 'การดำเนินการไม่ถูกต้อง')
            return redirect('projects:delete_request_list')

        delete_req.reviewed_by = request.user
        delete_req.reviewed_at = timezone.now()
        delete_req.review_remark = remark

        if action == 'approve':
            delete_req.status = 'approved'
            delete_req.save()
            project_name = delete_req.project.name
            project_code = delete_req.project.project_code
            log_action(
                actor=request.user, action='PROJECT_DELETE_APPROVE',
                target_repr=f'{project_code} - {project_name}',
                detail=f'หมายเหตุ: {remark}',
                ip_address=get_client_ip(request),
            )
            delete_req.project.delete()
            messages.success(request, f'อนุมัติและลบโครงการ "{project_name}" แล้ว')
        else:
            delete_req.status = 'rejected'
            delete_req.save()
            log_action(
                actor=request.user, action='PROJECT_DELETE_REJECT',
                target_repr=f'{delete_req.project.project_code} - {delete_req.project.name}',
                detail=f'หมายเหตุ: {remark}',
                ip_address=get_client_ip(request),
            )
            messages.info(request, f'ปฏิเสธคำขอลบโครงการ "{delete_req.project.name}" แล้ว')

        return redirect('projects:delete_request_list')

    return render(request, 'projects/delete_request_review.html', {
        'delete_req': delete_req,
    })


@role_required(['planner', 'head', 'admin'])
def budget_transfer(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=project_pk).exists():
        raise PermissionDenied

    if request.method == 'POST':
        form = BudgetTransferForm(request.POST, project=project)
        if form.is_valid():
            from_act = form.cleaned_data['from_activity']
            to_act = form.cleaned_data['to_activity']
            budget_type = form.cleaned_data['budget_type']
            amount = form.cleaned_data['amount']
            reason = form.cleaned_data['reason']

            with transaction.atomic():
                # Lock both rows
                from_act = Activity.objects.select_for_update().get(pk=from_act.pk)
                to_act = Activity.objects.select_for_update().get(pk=to_act.pk)

                # Deduct from source
                field = f'budget_{budget_type}'
                setattr(from_act, field, getattr(from_act, field) - amount)
                from_act.save()

                # Add to destination
                setattr(to_act, field, getattr(to_act, field) + amount)
                to_act.save()

                # Record transfer
                transfer = BudgetTransfer.objects.create(
                    project=project,
                    from_activity=from_act,
                    to_activity=to_act,
                    budget_type=budget_type,
                    amount=amount,
                    reason=reason,
                    transferred_by=request.user,
                )

            log_action(
                actor=request.user, action='BUDGET_TRANSFER',
                target_repr=f'{project.project_code} — {from_act.name} → {to_act.name}',
                detail=(
                    f'หมวด: {transfer.get_budget_type_display()} | '
                    f'จำนวน: {amount:,.2f} บาท | เหตุผล: {reason}'
                ),
                ip_address=get_client_ip(request),
            )
            messages.success(
                request,
                f'โอนงบประมาณ {amount:,.2f} บาท ({transfer.get_budget_type_display()}) '
                f'จาก "{from_act.name}" ไป "{to_act.name}" สำเร็จ'
            )
            return redirect('projects:project_detail', pk=project_pk)
    else:
        form = BudgetTransferForm(project=project)

    transfers = BudgetTransfer.objects.filter(project=project).select_related(
        'from_activity', 'to_activity', 'transferred_by'
    )[:20]

    return render(request, 'projects/budget_transfer_form.html', {
        'project': project,
        'form': form,
        'transfers': transfers,
    })


@login_required
def budget_transfer_history(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=project_pk).exists():
        raise PermissionDenied

    transfers = BudgetTransfer.objects.filter(project=project).select_related(
        'from_activity', 'to_activity', 'transferred_by'
    )
    return render(request, 'projects/budget_transfer_history.html', {
        'project': project,
        'transfers': transfers,
    })
