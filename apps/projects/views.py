import calendar as cal
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import FloatField, Q
from django.db.models.functions import Cast
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

    projects = projects.prefetch_related('budget_sources').annotate(
        code_num=Cast('project_code', FloatField())
    ).order_by('code_num', 'project_code')

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

    activities = project.activities.prefetch_related('responsible_persons', 'notify_persons').all()
    recent_expenses = Expense.objects.filter(
        activity__project=project
    ).select_related('activity', 'created_by').order_by('-created_at')[:10]

    activities = list(activities)

    # สรุปแหล่งเงิน: จัดสรร / ใช้ไป / เหลือ
    source_summary = []
    total_tagged = 0
    for source in project.budget_sources.all():
        spent = project.spent_by_source(source.source_type)
        total_tagged += spent
        source_summary.append({
            'label': source.get_source_type_display(),
            'source_type': source.source_type,
            'amount': source.amount,
            'spent': spent,
            'remaining': source.amount - spent,
        })
    # ยอดที่ยังไม่ระบุแหล่งเงิน
    untagged_spent = project.total_spent - total_tagged

    context = {
        'project': project,
        'activities': activities,
        'recent_expenses': recent_expenses,
        'untagged_spent': untagged_spent,
        'source_summary': source_summary,
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

    # สรุปแหล่งเงินต่อกิจกรรม: จัดสรร / ใช้จริง (จาก expense ที่มี budget_source) / เหลือ
    from django.db.models import Sum as _Sum
    src_spent = {
        row['budget_source']: row['total']
        for row in Expense.objects.filter(
            activity=activity, status='approved',
            budget_source__in=['government', 'accumulated', 'revenue'],
        ).values('budget_source').annotate(total=_Sum('amount'))
    }
    SOURCE_LABELS = {'government': 'เงินแผ่นดิน', 'accumulated': 'เงินสะสม', 'revenue': 'เงินรายได้'}
    source_summary = []
    for src, label in SOURCE_LABELS.items():
        allocated = getattr(activity, f'budget_{src}', 0)
        if allocated:
            spent = src_spent.get(src, 0)
            source_summary.append({
                'label': label,
                'allocated': allocated,
                'spent': spent,
                'remaining': allocated - spent,
            })

    # --- Deadline & Budget alerts ---
    from django.utils import timezone as _tz
    from datetime import date as _date
    today = _date.today()
    days_to_end = (activity.end_date - today).days if activity.end_date else None
    deadline_overdue = days_to_end is not None and days_to_end < 0 and activity.status not in ('completed', 'cancelled')
    deadline_soon    = days_to_end is not None and 0 <= days_to_end <= 7 and activity.status not in ('completed', 'cancelled')

    budget_full_not_done = (
        not activity.no_budget and
        activity.budget_usage_percent >= 100 and
        activity.status not in ('completed', 'cancelled')
    )
    approved_expenses = expenses.filter(status='approved')
    unlinked_count = approved_expenses.filter(activity_report__isnull=True).count()
    has_reports = reports.count() > 0
    # alert เมื่อมี expense ที่ไม่มีรายงานรองรับ ไม่ว่าจะมีรายงานอยู่แล้วหรือไม่
    unlinked_alert = unlinked_count > 0

    # --- Status Timeline ---
    from apps.accounts.models import AuditLog
    from django.db.models import Q as _Q
    activity_logs = AuditLog.objects.filter(
        action__in=['ACTIVITY_STATUS', 'ACTIVITY_CREATE'],
    ).filter(
        _Q(target_repr__contains=f'กิจกรรม {activity.activity_number}:') |
        _Q(target_repr__contains=f'กิจกรรมที่ {activity.activity_number} -')
    ).filter(
        target_repr__startswith=str(project.project_code)
    ).select_related('user').order_by('created_at')

    STATUS_LABELS = {
        'pending': 'รอดำเนินการ',
        'in_progress': 'กำลังดำเนินการ',
        'completed': 'เสร็จสิ้น',
        'cancelled': 'ยกเลิก',
    }
    STATUS_ORDER = ['pending', 'in_progress', 'completed']

    # map status → most recent log that transitioned TO that status
    status_events = {}
    create_event = None
    for log in activity_logs:
        if log.action == 'ACTIVITY_CREATE':
            create_event = log
        elif log.action == 'ACTIVITY_STATUS':
            try:
                new_s = log.detail.split('→')[-1].strip()
                status_events[new_s] = log
            except Exception:
                pass

    current_idx = STATUS_ORDER.index(activity.status) if activity.status in STATUS_ORDER else 0
    timeline = []
    if create_event:
        timeline.append({'type': 'create', 'label': 'สร้างกิจกรรม', 'done': True, 'active': False,
                         'user': create_event.user, 'date': create_event.created_at})
    for i, s in enumerate(STATUS_ORDER):
        log = status_events.get(s)
        is_current = (s == activity.status)
        is_done = (i < current_idx) or (is_current and s == 'completed')
        timeline.append({'type': 'status', 'status': s, 'label': STATUS_LABELS[s],
                         'done': is_done, 'active': is_current,
                         'user': log.user if log else None,
                         'date': log.created_at if log else None})

    role = getattr(getattr(request.user, 'profile', None), 'role', 'staff')
    can_change_status = (
        role in ('planner', 'head', 'admin') or
        activity.responsible_persons.filter(pk=request.user.pk).exists()
    )

    context = {
        'project': project,
        'activity': activity,
        'expenses': expenses,
        'reports': reports,
        'source_summary': source_summary,
        # deadline & alerts
        'days_to_end': days_to_end,
        'deadline_overdue': deadline_overdue,
        'deadline_soon': deadline_soon,
        'budget_full_not_done': budget_full_not_done,
        'unlinked_count': unlinked_count,
        'unlinked_alert': unlinked_alert,
        'has_reports': has_reports,
        # timeline
        'timeline': timeline,
        'can_change_status': can_change_status,
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

    # expense ที่ approved และยังไม่ผูกกับรายงานใด
    linkable_expenses = Expense.objects.filter(
        activity=activity, status='approved', activity_report__isnull=True
    ).order_by('expense_date')

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
            # ผูก expense ที่เลือก
            selected_ids = request.POST.getlist('link_expenses')
            if selected_ids:
                Expense.objects.filter(
                    pk__in=selected_ids, activity=activity, status='approved'
                ).update(activity_report=report)
            messages.success(request, f'บันทึกรายงานครั้งที่ {report.round_number} สำเร็จ')
            return redirect('projects:activity_detail',
                            project_pk=activity.project_id, pk=activity.pk)
    else:
        form = ActivityReportForm()

    return render(request, 'projects/activity_report_form.html', {
        'form': form,
        'activity': activity,
        'project': activity.project,
        'linkable_expenses': linkable_expenses,
        'title': 'บันทึกรายงานกิจกรรมย่อย',
    })


@login_required
def activity_report_edit(request, pk):
    report = get_object_or_404(ActivityReport, pk=pk)
    activity = report.activity
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=activity.project_id).exists():
        raise PermissionDenied

    # expense ที่ผูกอยู่แล้ว + ที่ยังไม่ผูก (รวมกันเพื่อแสดง)
    linked_expenses = Expense.objects.filter(
        activity=activity, status='approved', activity_report=report
    ).order_by('expense_date')
    linkable_expenses = Expense.objects.filter(
        activity=activity, status='approved', activity_report__isnull=True
    ).order_by('expense_date')

    if request.method == 'POST':
        form = ActivityReportForm(request.POST, request.FILES, instance=report)
        if form.is_valid():
            form.save()
            # อัปเดต expense links: unlink ที่ถูก uncheck, link ที่ถูก check
            selected_ids = set(request.POST.getlist('link_expenses'))
            linked_ids = set(str(e.pk) for e in linked_expenses)
            # unlink ที่ถูกเอาออก
            to_unlink = linked_ids - selected_ids
            if to_unlink:
                Expense.objects.filter(pk__in=to_unlink).update(activity_report=None)
            # link ใหม่
            to_link = selected_ids - linked_ids
            if to_link:
                Expense.objects.filter(
                    pk__in=to_link, activity=activity, status='approved'
                ).update(activity_report=report)
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
        'linked_expenses': linked_expenses,
        'linkable_expenses': linkable_expenses,
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


@role_required(['planner', 'head', 'admin'])
def activity_status_change(request, project_pk, pk):
    if request.method != 'POST':
        raise PermissionDenied

    project = get_object_or_404(Project, pk=project_pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=project_pk).exists():
        raise PermissionDenied

    activity = get_object_or_404(Activity, pk=pk, project=project)
    new_status = request.POST.get('status')
    valid_statuses = [s[0] for s in Activity.STATUS_CHOICES]
    if new_status not in valid_statuses:
        messages.error(request, 'สถานะไม่ถูกต้อง')
        return redirect('projects:activity_detail', project_pk=project_pk, pk=pk)

    old_status = activity.status
    activity.status = new_status
    activity.save()
    log_action(
        actor=request.user, action='ACTIVITY_STATUS',
        target_repr=f'{project.project_code} / กิจกรรมที่ {activity.activity_number} - {activity.name}',
        detail=f'สถานะ: {old_status} → {new_status}',
        ip_address=get_client_ip(request),
    )
    messages.success(request, f'เปลี่ยนสถานะกิจกรรมเป็น "{activity.get_status_display()}" สำเร็จ')
    return redirect('projects:activity_detail', project_pk=project_pk, pk=pk)


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


@login_required
def project_timeline(request):
    THAI_MONTHS = {
        1: 'ม.ค.', 2: 'ก.พ.', 3: 'มี.ค.', 4: 'เม.ย.',
        5: 'พ.ค.', 6: 'มิ.ย.', 7: 'ก.ค.', 8: 'ส.ค.',
        9: 'ก.ย.', 10: 'ต.ค.', 11: 'พ.ย.', 12: 'ธ.ค.'
    }

    today = timezone.now().date()
    fiscal_years = FiscalYear.objects.all().order_by('-year')
    fiscal_year_id = request.GET.get('fiscal_year')

    if fiscal_year_id:
        fiscal_year = fiscal_years.filter(pk=fiscal_year_id).first()
    else:
        fiscal_year = fiscal_years.filter(is_active=True).first() or fiscal_years.first()

    if not fiscal_year:
        return render(request, 'projects/timeline.html', {
            'fiscal_years': fiscal_years,
            'fiscal_year': None,
            'months': [],
            'rows': [],
        })

    # Build 12-month columns for fiscal year (Oct → Sep)
    fy_gregorian = fiscal_year.year - 543
    fy_start_gregorian = fy_gregorian - 1

    months = []
    for i in range(12):
        m = (9 + i) % 12 + 1
        y = fy_start_gregorian if m >= 10 else fy_gregorian
        m_start = date(y, m, 1)
        m_end = date(y, m, cal.monthrange(y, m)[1])
        months.append({
            'label': THAI_MONTHS[m],
            'month': m,
            'year': y,
            'start': m_start,
            'end': m_end,
            'is_current': (today.year == y and today.month == m),
        })

    def get_cell_style(status, overdue, is_current):
        if overdue:
            return ('bg-red-500', 'text-white') if is_current else ('bg-red-200', 'text-red-800')
        mapping = {
            'draft':       (('bg-slate-500', 'text-white'),   ('bg-slate-200', 'text-slate-700')),
            'not_started': (('bg-amber-400', 'text-white'),   ('bg-amber-100', 'text-amber-800')),
            'pending':     (('bg-amber-400', 'text-white'),   ('bg-amber-100', 'text-amber-800')),
            'in_progress': (('bg-blue-600',  'text-white'),   ('bg-blue-200',  'text-blue-800')),
            'active':      (('bg-blue-600',  'text-white'),   ('bg-blue-200',  'text-blue-800')),
            'completed':   (('bg-emerald-500', 'text-white'), ('bg-emerald-200', 'text-emerald-800')),
            'cancelled':   (('bg-slate-300', 'text-slate-500'), ('bg-slate-100', 'text-slate-400')),
        }
        pair = mapping.get(status, (('bg-gray-400', 'text-white'), ('bg-gray-200', 'text-gray-700')))
        bg, fg = pair[0] if is_current else pair[1]
        return bg, fg

    def build_cells(start, end, status, overdue):
        cells = []
        for m in months:
            overlaps = bool(start and end and start <= m['end'] and end >= m['start'])
            if overlaps:
                bg, fg = get_cell_style(status, overdue, m['is_current'])
            else:
                bg, fg = '', ''
            cells.append({'overlaps': overlaps, 'bg': bg, 'fg': fg, 'is_current': m['is_current']})
        return cells

    projects = get_projects_for_user(request.user).filter(
        fiscal_year=fiscal_year
    ).prefetch_related(
        'activities', 'responsible_persons',
    ).annotate(
        code_num=Cast('project_code', FloatField())
    ).order_by('code_num', 'project_code')

    rows = []
    for project in projects:
        proj_overdue = bool(
            project.end_date and
            project.end_date < today and
            project.status not in ('completed', 'cancelled')
        )
        rows.append({
            'type': 'project',
            'obj': project,
            'cells': build_cells(project.start_date, project.end_date, project.status, proj_overdue),
            'overdue': proj_overdue,
        })
        for activity in project.activities.all().order_by('activity_number'):
            act_overdue = bool(
                activity.end_date and
                activity.end_date < today and
                activity.status not in ('completed', 'cancelled')
            )
            rows.append({
                'type': 'activity',
                'obj': activity,
                'project': project,
                'cells': build_cells(activity.start_date, activity.end_date, activity.status, act_overdue),
                'overdue': act_overdue,
            })

    return render(request, 'projects/timeline.html', {
        'months': months,
        'rows': rows,
        'fiscal_year': fiscal_year,
        'fiscal_years': fiscal_years,
        'today': today,
    })
