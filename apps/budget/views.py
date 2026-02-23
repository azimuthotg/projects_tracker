from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.audit import get_client_ip, log_action
from apps.accounts.decorators import role_required
from apps.projects.utils import get_projects_for_user

from .forms import ExpenseApprovalForm, ExpenseAttachmentForm, ExpenseForm
from .models import Expense, ExpenseAttachment, ExpenseComment
from .utils import get_expenses_for_user


@login_required
def expense_list(request):
    expenses = get_expenses_for_user(request.user)

    status = request.GET.get('status')
    search = request.GET.get('search')

    if status:
        expenses = expenses.filter(status=status)
    if search:
        expenses = expenses.filter(description__icontains=search)

    expenses = expenses.select_related(
        'activity__project', 'created_by', 'approved_by'
    )

    context = {
        'expenses': expenses,
        'status_choices': Expense.STATUS_CHOICES,
        'current_status': status,
        'current_search': search or '',
    }
    return render(request, 'budget/expense_list.html', context)


@login_required
def expense_create(request, activity_pk=None):
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, activity_pk=activity_pk)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            projects = get_projects_for_user(request.user)
            if not projects.filter(pk=expense.activity.project_id).exists():
                raise PermissionDenied
            expense.save()
            log_action(
                actor=request.user, action='EXPENSE_CREATE',
                target_repr=f'{expense.activity.project.project_code} / {expense.activity.name} — {expense.description}',
                detail=f'จำนวน: {expense.amount} บาท',
                ip_address=get_client_ip(request),
            )
            messages.success(request, 'บันทึกรายการเบิกจ่ายสำเร็จ')
            return redirect('projects:activity_detail',
                            project_pk=expense.activity.project_id,
                            pk=expense.activity_id)
    else:
        initial = {}
        if activity_pk:
            initial['activity'] = activity_pk
        form = ExpenseForm(initial=initial, activity_pk=activity_pk)

    projects = get_projects_for_user(request.user)
    from apps.projects.models import Activity
    form.fields['activity'].queryset = Activity.objects.filter(
        project__in=projects,
        status__in=['pending', 'in_progress'],
    )

    return render(request, 'budget/expense_form.html', {
        'form': form,
        'activity_pk': activity_pk,
        'title': 'บันทึกรายการเบิกจ่าย',
    })


@login_required
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk)

    if expense.status != 'pending':
        messages.error(request, 'ไม่สามารถแก้ไขรายการที่ได้รับการอนุมัติหรือไม่อนุมัติแล้ว')
        return redirect('budget:expense_list')
    if expense.created_by != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            form.save()
            log_action(
                actor=request.user, action='EXPENSE_UPDATE',
                target_repr=f'{expense.activity.project.project_code} / {expense.activity.name} — {expense.description}',
                detail=f'จำนวน: {expense.amount} บาท',
                ip_address=get_client_ip(request),
            )
            messages.success(request, 'แก้ไขรายการเบิกจ่ายสำเร็จ')
            return redirect('projects:activity_detail',
                            project_pk=expense.activity.project_id,
                            pk=expense.activity_id)
    else:
        form = ExpenseForm(instance=expense)

    projects = get_projects_for_user(request.user)
    from apps.projects.models import Activity, ActivityReport
    form.fields['activity'].queryset = Activity.objects.filter(
        project__in=projects,
        status__in=['pending', 'in_progress'],
    )
    form.fields['activity_report'].queryset = ActivityReport.objects.filter(
        activity=expense.activity
    )
    form.fields['activity_report'].label_from_instance = (
        lambda r: f'ครั้งที่ {r.round_number}: {r.title} ({r.date.strftime("%d/%m/%Y")})'
    )

    return render(request, 'budget/expense_form.html', {
        'form': form,
        'expense': expense,
        'title': 'แก้ไขรายการเบิกจ่าย',
    })


@login_required
def expense_link_report(request, pk):
    """ผูก/ยกเลิกผูกรายการเบิกจ่ายกับรายงานกิจกรรมย่อย (ไม่ขึ้นกับสถานะการอนุมัติ)"""
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    expense = get_object_or_404(Expense, pk=pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=expense.activity.project_id).exists():
        raise PermissionDenied

    report_id = request.POST.get('activity_report') or None
    if report_id:
        from apps.projects.models import ActivityReport
        report = get_object_or_404(ActivityReport, pk=report_id, activity=expense.activity)
        expense.activity_report = report
        messages.success(request, f'ผูกกับรายงานครั้งที่ {report.round_number} สำเร็จ')
    else:
        expense.activity_report = None
        messages.success(request, 'ยกเลิกการผูกรายงานแล้ว')

    expense.save(update_fields=['activity_report'])
    return redirect('projects:activity_detail',
                    project_pk=expense.activity.project_id,
                    pk=expense.activity_id)


@login_required
def expense_delete(request, pk):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    expense = get_object_or_404(Expense, pk=pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=expense.activity.project_id).exists():
        raise PermissionDenied

    role = getattr(getattr(request.user, 'profile', None), 'role', 'staff')

    # pending: ผู้สร้างหรือ head/admin ลบได้
    # approved/rejected: admin เท่านั้น
    can_delete = False
    if expense.status == 'pending':
        can_delete = (expense.created_by == request.user) or role in ('head', 'admin')
    else:
        can_delete = role == 'admin'

    if not can_delete:
        raise PermissionDenied

    project_pk = expense.activity.project_id
    activity_pk = expense.activity_id
    expense_repr = f'{expense.activity.project.project_code} / {expense.activity.name} — {expense.description}'
    expense_amount = expense.amount
    expense.delete()
    log_action(
        actor=request.user, action='EXPENSE_DELETE',
        target_repr=expense_repr,
        detail=f'จำนวน: {expense_amount} บาท',
        ip_address=get_client_ip(request),
    )
    messages.success(request, 'ลบรายการเบิกจ่ายสำเร็จ')
    return redirect('projects:activity_detail', project_pk=project_pk, pk=activity_pk)


@role_required(['head', 'admin'])
def approval_list(request):
    expenses = get_expenses_for_user(request.user).filter(status='pending')
    expenses = expenses.select_related(
        'activity__project', 'created_by'
    )

    return render(request, 'budget/approval_list.html', {
        'expenses': expenses,
    })


@role_required(['head', 'admin'])
def expense_approve(request, pk):
    expense = get_object_or_404(Expense, pk=pk, status='pending')

    # Verify access
    expenses = get_expenses_for_user(request.user)
    if not expenses.filter(pk=pk).exists():
        raise PermissionDenied

    if request.method == 'POST':
        form = ExpenseApprovalForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            expense.status = action
            expense.approved_by = request.user
            expense.approved_at = timezone.now()
            expense.remark = form.cleaned_data.get('remark', '')
            expense.save()

            audit_action = 'EXPENSE_APPROVE' if action == 'approved' else 'EXPENSE_REJECT'
            log_action(
                actor=request.user, action=audit_action,
                target_repr=f'{expense.activity.project.project_code} / {expense.activity.name} — {expense.description}',
                detail=f'จำนวน: {expense.amount} บาท | หมายเหตุ: {expense.remark}',
                ip_address=get_client_ip(request),
            )
            status_text = 'อนุมัติ' if action == 'approved' else 'ไม่อนุมัติ'
            messages.success(request, f'{status_text}รายการเบิกจ่ายสำเร็จ')
            return redirect('budget:approval_list')
    else:
        form = ExpenseApprovalForm()

    comments = expense.comments.select_related('created_by').all()
    attachments = expense.attachments.select_related('uploaded_by').all()
    attach_form = ExpenseAttachmentForm()

    return render(request, 'budget/expense_approve.html', {
        'expense': expense,
        'form': form,
        'comments': comments,
        'attachments': attachments,
        'attach_form': attach_form,
    })


@login_required
def expense_comment_add(request, pk):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    expense = get_object_or_404(Expense, pk=pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=expense.activity.project_id).exists():
        raise PermissionDenied

    text = request.POST.get('text', '').strip()
    if text:
        ExpenseComment.objects.create(
            expense=expense,
            text=text,
            created_by=request.user,
        )
        messages.success(request, 'บันทึกความเห็นแล้ว')
    else:
        messages.error(request, 'กรุณากรอกความเห็น')

    # Redirect back — support both approve page and activity_detail
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('projects:activity_detail',
                    project_pk=expense.activity.project_id,
                    pk=expense.activity_id)


@login_required
def expense_attachment_add(request, pk):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    expense = get_object_or_404(Expense, pk=pk)
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=expense.activity.project_id).exists():
        raise PermissionDenied

    form = ExpenseAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.expense = expense
        attachment.uploaded_by = request.user
        uploaded = request.FILES.get('file')
        if uploaded:
            attachment.original_filename = uploaded.name
        attachment.save()
        messages.success(request, f'อัพโหลดไฟล์ "{attachment.original_filename}" สำเร็จ')
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('projects:activity_detail',
                    project_pk=expense.activity.project_id,
                    pk=expense.activity_id)


@login_required
def expense_attachment_delete(request, pk):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    attachment = get_object_or_404(ExpenseAttachment, pk=pk)
    expense = attachment.expense
    projects = get_projects_for_user(request.user)
    if not projects.filter(pk=expense.activity.project_id).exists():
        raise PermissionDenied

    role = getattr(getattr(request.user, 'profile', None), 'role', 'staff')
    if attachment.uploaded_by != request.user and role != 'admin':
        raise PermissionDenied

    filename = attachment.original_filename or attachment.file.name
    attachment.file.delete(save=False)
    attachment.delete()
    messages.success(request, f'ลบไฟล์ "{filename}" แล้ว')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('projects:activity_detail',
                    project_pk=expense.activity.project_id,
                    pk=expense.activity_id)
