from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .audit import get_client_ip, log_action
from .decorators import role_required
from .forms import (
    ApprovedOrganizationForm,
    DepartmentForm,
    FiscalYearForm,
    LoginForm,
    PasswordResetByAdminForm,
    UserCreateForm,
    UserEditForm,
)
from .models import ApprovedOrganization, AuditLog, Department, UserProfile
from apps.projects.models import FiscalYear, Project
from apps.budget.models import Expense


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = LoginForm


class CustomLogoutView(LogoutView):
    pass


# ── User Profile ─────────────────────────────────────────────────────

@login_required
def my_profile(request):
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user, defaults={'role': 'staff'}
    )
    return render(request, 'accounts/profile.html', {'profile': profile})


# ── Admin Management Dashboard ──────────────────────────────────────

@role_required(['admin'])
def manage_dashboard(request):
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    total_departments = Department.objects.count()
    total_projects = Project.objects.count()
    active_fiscal = FiscalYear.objects.filter(is_active=True).first()
    pending_expenses = Expense.objects.filter(status='pending').count()

    departments = Department.objects.annotate(
        member_count=Count('members'),
        project_count=Count('projects'),
    )

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'total_departments': total_departments,
        'total_projects': total_projects,
        'active_fiscal': active_fiscal,
        'pending_expenses': pending_expenses,
        'departments': departments,
    }
    return render(request, 'manage/dashboard.html', context)


# ── User Management ─────────────────────────────────────────────────

@role_required(['admin'])
def user_list(request):
    users = User.objects.select_related('profile', 'profile__department').all()

    # Filters
    dept_id = request.GET.get('department')
    role = request.GET.get('role')
    search = request.GET.get('search', '').strip()

    if dept_id:
        users = users.filter(profile__department_id=dept_id)
    if role:
        users = users.filter(profile__role=role)
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    context = {
        'users': users,
        'departments': Department.objects.all(),
        'role_choices': UserProfile.ROLE_CHOICES,
        'current_dept': dept_id or '',
        'current_role': role or '',
        'current_search': search,
    }
    return render(request, 'manage/user_list.html', context)


@role_required(['admin'])
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'สร้างผู้ใช้ "{user.username}" สำเร็จ')
            return redirect('accounts:user_list')
    else:
        form = UserCreateForm()
    return render(request, 'manage/user_form.html', {'form': form, 'is_edit': False})


@role_required(['admin'])
def user_edit(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    pw_form = PasswordResetByAdminForm()

    if request.method == 'POST':
        if 'reset_password' in request.POST:
            pw_form = PasswordResetByAdminForm(request.POST)
            if pw_form.is_valid():
                target_user.set_password(pw_form.cleaned_data['new_password'])
                target_user.save()
                log_action(
                    actor=request.user, action='USER_PASSWORD_RESET',
                    target_repr=target_user.username,
                    detail=f'รีเซ็ตรหัสผ่านของ {target_user.username}',
                    ip_address=get_client_ip(request), target_user=target_user,
                )
                # เปลี่ยน source เป็น manual ถ้าเดิมเป็น npu_api
                if hasattr(target_user, 'profile') and target_user.profile.source == 'npu_api':
                    target_user.profile.source = 'manual'
                    target_user.profile.save(update_fields=['source'])
                    log_action(
                        actor=request.user, action='USER_SOURCE_CHANGE',
                        target_repr=target_user.username,
                        detail=f'เปลี่ยน source จาก npu_api → manual',
                        ip_address=get_client_ip(request), target_user=target_user,
                    )
                    messages.success(request, f'รีเซ็ตรหัสผ่านของ "{target_user.username}" สำเร็จ (เปลี่ยนเป็น Local User)')
                else:
                    messages.success(request, f'รีเซ็ตรหัสผ่านของ "{target_user.username}" สำเร็จ')
                return redirect('accounts:user_edit', pk=pk)
            form = UserEditForm(user_instance=target_user)
        else:
            old_role = getattr(getattr(target_user, 'profile', None), 'role', None)
            form = UserEditForm(request.POST, user_instance=target_user)
            if form.is_valid():
                form.save()
                new_role = getattr(getattr(target_user, 'profile', None), 'role', None)
                if old_role and new_role and old_role != new_role:
                    log_action(
                        actor=request.user, action='USER_ROLE_CHANGE',
                        target_repr=target_user.username,
                        detail=f'เปลี่ยนบทบาท {old_role} → {new_role}',
                        ip_address=get_client_ip(request), target_user=target_user,
                    )
                messages.success(request, f'แก้ไขผู้ใช้ "{target_user.username}" สำเร็จ')
                return redirect('accounts:user_list')
    else:
        form = UserEditForm(user_instance=target_user)

    return render(request, 'manage/user_form.html', {
        'form': form,
        'pw_form': pw_form,
        'is_edit': True,
        'target_user': target_user,
    })


@role_required(['admin'])
def user_toggle_active(request, pk):
    if request.method != 'POST':
        return redirect('accounts:user_list')
    target_user = get_object_or_404(User, pk=pk)
    if target_user == request.user:
        messages.error(request, 'ไม่สามารถปิดการใช้งานตัวเองได้')
        return redirect('accounts:user_list')
    target_user.is_active = not target_user.is_active
    target_user.save()
    status = 'เปิดใช้งาน' if target_user.is_active else 'ปิดใช้งาน'
    log_action(
        actor=request.user, action='USER_TOGGLE_ACTIVE',
        target_repr=target_user.username,
        detail=f'{status}ผู้ใช้ {target_user.username}',
        ip_address=get_client_ip(request), target_user=target_user,
    )
    messages.success(request, f'{status}ผู้ใช้ "{target_user.username}" สำเร็จ')
    return redirect('accounts:user_list')


# ── Department Management ────────────────────────────────────────────

@role_required(['admin'])
def department_list(request):
    departments = Department.objects.annotate(
        member_count=Count('members'),
        project_count=Count('projects'),
    )
    return render(request, 'manage/department_list.html', {'departments': departments})


@role_required(['admin'])
def department_create(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save()
            messages.success(request, f'สร้างแผนก "{dept.name}" สำเร็จ')
            return redirect('accounts:department_list')
    else:
        form = DepartmentForm()
    return render(request, 'manage/department_form.html', {'form': form, 'is_edit': False})


@role_required(['admin'])
def department_edit(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            form.save()
            messages.success(request, f'แก้ไขแผนก "{dept.name}" สำเร็จ')
            return redirect('accounts:department_list')
    else:
        form = DepartmentForm(instance=dept)
    return render(request, 'manage/department_form.html', {'form': form, 'is_edit': True, 'department': dept})


@role_required(['admin'])
def department_delete(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    member_count = dept.members.count()
    project_count = dept.projects.count()
    has_references = member_count > 0 or project_count > 0

    if request.method == 'POST':
        if has_references:
            messages.error(request, f'ไม่สามารถลบแผนกนี้ได้ เนื่องจากมีสมาชิก {member_count} คน และโครงการ {project_count} โครงการ อ้างอิงอยู่')
            return redirect('accounts:department_list')
        name = dept.name
        dept.delete()
        messages.success(request, f'ลบแผนก "{name}" สำเร็จ')
        return redirect('accounts:department_list')

    return render(request, 'manage/department_confirm_delete.html', {
        'department': dept,
        'member_count': member_count,
        'project_count': project_count,
        'has_references': has_references,
    })


# ── Fiscal Year Management ───────────────────────────────────────────

@role_required(['admin'])
def fiscalyear_list(request):
    fiscal_years = FiscalYear.objects.annotate(
        project_count=Count('projects'),
    )
    return render(request, 'manage/fiscalyear_list.html', {'fiscal_years': fiscal_years})


@role_required(['admin'])
def fiscalyear_create(request):
    if request.method == 'POST':
        form = FiscalYearForm(request.POST)
        if form.is_valid():
            fy = form.save(commit=False)
            if fy.is_active:
                FiscalYear.objects.filter(is_active=True).update(is_active=False)
            fy.save()
            messages.success(request, f'สร้างปีงบประมาณ {fy.year} สำเร็จ')
            return redirect('accounts:fiscalyear_list')
    else:
        form = FiscalYearForm()
    return render(request, 'manage/fiscalyear_form.html', {'form': form, 'is_edit': False})


@role_required(['admin'])
def fiscalyear_edit(request, pk):
    fy = get_object_or_404(FiscalYear, pk=pk)
    if request.method == 'POST':
        form = FiscalYearForm(request.POST, instance=fy)
        if form.is_valid():
            fy = form.save(commit=False)
            if fy.is_active:
                FiscalYear.objects.filter(is_active=True).exclude(pk=fy.pk).update(is_active=False)
            fy.save()
            messages.success(request, f'แก้ไขปีงบประมาณ {fy.year} สำเร็จ')
            return redirect('accounts:fiscalyear_list')
    else:
        form = FiscalYearForm(instance=fy)
    return render(request, 'manage/fiscalyear_form.html', {'form': form, 'is_edit': True, 'fiscalyear': fy})


@role_required(['admin'])
def fiscalyear_toggle(request, pk):
    if request.method != 'POST':
        return redirect('accounts:fiscalyear_list')
    fy = get_object_or_404(FiscalYear, pk=pk)
    if fy.is_active:
        fy.is_active = False
        fy.save()
        messages.success(request, f'ปิดใช้งานปีงบประมาณ {fy.year} สำเร็จ')
    else:
        FiscalYear.objects.filter(is_active=True).update(is_active=False)
        fy.is_active = True
        fy.save()
        messages.success(request, f'เปิดใช้งานปีงบประมาณ {fy.year} สำเร็จ')
    return redirect('accounts:fiscalyear_list')


@role_required(['admin'])
def fiscalyear_delete(request, pk):
    fy = get_object_or_404(FiscalYear, pk=pk)
    project_count = fy.projects.count()

    if request.method == 'POST':
        if project_count > 0:
            messages.error(request, f'ไม่สามารถลบปีงบประมาณนี้ได้ เนื่องจากมี {project_count} โครงการอ้างอิงอยู่')
            return redirect('accounts:fiscalyear_list')
        year = fy.year
        fy.delete()
        messages.success(request, f'ลบปีงบประมาณ {year} สำเร็จ')
        return redirect('accounts:fiscalyear_list')

    return render(request, 'manage/fiscalyear_confirm_delete.html', {
        'fiscalyear': fy,
        'project_count': project_count,
    })


# ── Approved Organizations ───────────────────────────────────────────

@role_required(['admin'])
def approved_org_list(request):
    orgs = ApprovedOrganization.objects.all()
    return render(request, 'manage/approved_org_list.html', {'orgs': orgs})


@role_required(['admin'])
def approved_org_create(request):
    if request.method == 'POST':
        form = ApprovedOrganizationForm(request.POST)
        if form.is_valid():
            org = form.save()
            messages.success(request, f'เพิ่มหน่วยงาน "{org.name}" สำเร็จ')
            return redirect('accounts:approved_org_list')
    else:
        form = ApprovedOrganizationForm()

    # Distinct org names from pending users that are not yet approved
    existing_names = ApprovedOrganization.objects.values_list('name', flat=True)
    pending_orgs = (
        UserProfile.objects
        .filter(approval_status='pending')
        .exclude(organization='')
        .exclude(organization__in=existing_names)
        .values_list('organization', flat=True)
        .distinct()
        .order_by('organization')
    )

    return render(request, 'manage/approved_org_form.html', {
        'form': form,
        'is_edit': False,
        'pending_orgs': pending_orgs,
    })


@role_required(['admin'])
def approved_org_edit(request, pk):
    org = get_object_or_404(ApprovedOrganization, pk=pk)
    if request.method == 'POST':
        form = ApprovedOrganizationForm(request.POST, instance=org)
        if form.is_valid():
            form.save()
            messages.success(request, f'แก้ไขหน่วยงาน "{org.name}" สำเร็จ')
            return redirect('accounts:approved_org_list')
    else:
        form = ApprovedOrganizationForm(instance=org)
    return render(request, 'manage/approved_org_form.html', {'form': form, 'is_edit': True, 'org': org})


@role_required(['admin'])
def approved_org_delete(request, pk):
    org = get_object_or_404(ApprovedOrganization, pk=pk)
    if request.method == 'POST':
        name = org.name
        org.delete()
        messages.success(request, f'ลบหน่วยงาน "{name}" แล้ว')
        return redirect('accounts:approved_org_list')
    return render(request, 'manage/approved_org_confirm_delete.html', {'org': org})


# ── Pending Users ─────────────────────────────────────────────────────

@role_required(['admin'])
def pending_user_list(request):
    pending = User.objects.filter(
        profile__approval_status='pending', is_active=False
    ).select_related('profile', 'profile__department').order_by('date_joined')

    rejected = User.objects.filter(
        profile__approval_status='rejected'
    ).select_related('profile').order_by('-date_joined')[:20]

    return render(request, 'manage/pending_user_list.html', {
        'pending': pending,
        'rejected': rejected,
    })


@role_required(['admin'])
def pending_user_action(request, pk):
    if request.method != 'POST':
        return redirect('accounts:pending_user_list')

    target_user = get_object_or_404(User, pk=pk)
    action = request.POST.get('action')

    if action not in ('approve', 'reject'):
        messages.error(request, 'การดำเนินการไม่ถูกต้อง')
        return redirect('accounts:pending_user_list')

    profile = getattr(target_user, 'profile', None)
    if not profile:
        messages.error(request, 'ไม่พบโปรไฟล์ผู้ใช้')
        return redirect('accounts:pending_user_list')

    if action == 'approve':
        target_user.is_active = True
        target_user.save(update_fields=['is_active'])
        profile.approval_status = 'approved'
        profile.save(update_fields=['approval_status'])
        log_action(
            actor=request.user, action='USER_APPROVE',
            target_repr=target_user.get_full_name() or target_user.username,
            detail=f'หน่วยงาน: {profile.organization}',
            ip_address=get_client_ip(request), target_user=target_user,
        )
        messages.success(request, f'อนุมัติผู้ใช้ "{target_user.get_full_name() or target_user.username}" สำเร็จ')
    else:
        target_user.is_active = False
        target_user.save(update_fields=['is_active'])
        profile.approval_status = 'rejected'
        profile.save(update_fields=['approval_status'])
        log_action(
            actor=request.user, action='USER_REJECT',
            target_repr=target_user.get_full_name() or target_user.username,
            detail=f'หน่วยงาน: {profile.organization}',
            ip_address=get_client_ip(request), target_user=target_user,
        )
        messages.info(request, f'ปฏิเสธผู้ใช้ "{target_user.get_full_name() or target_user.username}" แล้ว')

    return redirect('accounts:pending_user_list')


# ── Audit Log ────────────────────────────────────────────────────────

@role_required(['admin'])
def audit_log_list(request):
    logs = AuditLog.objects.select_related('user', 'target_user').all()

    # Filters
    action = request.GET.get('action', '').strip()
    level = request.GET.get('level', '').strip()
    username = request.GET.get('username', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if action:
        logs = logs.filter(action=action)
    if level:
        logs = logs.filter(level=level)
    if username:
        logs = logs.filter(
            Q(user__username__icontains=username) |
            Q(target_repr__icontains=username)
        )
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)

    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'action_choices': AuditLog.ACTION_CHOICES,
        'level_choices': AuditLog.LEVEL_CHOICES,
        'current_action': action,
        'current_level': level,
        'current_username': username,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'total_count': logs.count(),
    }
    return render(request, 'manage/audit_log.html', context)
