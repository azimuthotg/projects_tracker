import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import Department
from apps.budget.models import Expense
from apps.budget.utils import get_expenses_for_user
from apps.projects.models import Activity, ActivityReport, FiscalYear, Project, ProjectBudgetSource
from apps.projects.utils import get_projects_for_user


@login_required
def index(request):
    context = {}

    if hasattr(request.user, 'profile'):
        profile = request.user.profile
        role = profile.role

        projects = get_projects_for_user(request.user)
        active_projects = projects.filter(status='active')
        expenses = get_expenses_for_user(request.user)

        # Budget totals
        total_budget = projects.aggregate(total=Sum('total_budget'))['total'] or 0
        total_spent = expenses.filter(status='approved').aggregate(
            total=Sum('amount')
        )['total'] or 0
        budget_usage = float(total_spent / total_budget * 100) if total_budget > 0 else 0

        # Pending approvals count (for head/admin)
        pending_approvals = 0
        if role in ('head', 'admin'):
            pending_approvals = expenses.filter(status='pending').count()

        # Recent expenses
        recent_expenses = expenses.select_related(
            'activity__project', 'created_by'
        ).order_by('-created_at')[:5]

        # Upcoming deadlines (activities ending within 7 days)
        today = timezone.now().date()
        deadline_soon = today + timedelta(days=7)
        if role == 'admin':
            upcoming_activities = Activity.objects.filter(
                end_date__gte=today, end_date__lte=deadline_soon,
                status__in=['pending', 'in_progress'],
            )
        elif role in ('planner', 'head'):
            upcoming_activities = Activity.objects.filter(
                project__department=profile.department,
                end_date__gte=today, end_date__lte=deadline_soon,
                status__in=['pending', 'in_progress'],
            )
        else:
            upcoming_activities = Activity.objects.filter(
                responsible_persons=request.user,
                end_date__gte=today, end_date__lte=deadline_soon,
                status__in=['pending', 'in_progress'],
            ).distinct()
        upcoming_activities = upcoming_activities.select_related('project')[:5]

        # --- รายการที่ต้องติดตาม (สำหรับ planner/head/admin) ---
        attention = {}
        if role in ('planner', 'head', 'admin'):
            if role == 'admin':
                scoped = Activity.objects.filter(project__in=projects)
            else:
                scoped = Activity.objects.filter(
                    project__department=profile.department,
                    project__in=projects,
                )

            # 1. กิจกรรม overdue (เลย deadline แล้วยังไม่เสร็จ)
            overdue_acts = scoped.filter(
                end_date__lt=today,
                status__in=['pending', 'in_progress'],
            ).select_related('project').order_by('end_date')[:8]

            # 2. งบเต็มแต่ยังไม่ปิดกิจกรรม (annotate total_spent)
            budget_full_acts = scoped.filter(
                status__in=['pending', 'in_progress'],
                no_budget=False,
                allocated_budget__gt=0,
            ).annotate(
                ann_spent=Sum('expenses__amount', filter=Q(expenses__status='approved'))
            ).filter(
                ann_spent__gte=F('allocated_budget')
            ).select_related('project')[:8]

            # 3. มี expense อนุมัติแล้ว แต่ไม่มีรายงานรองรับเลย
            no_report_acts = scoped.filter(
                expenses__status='approved',
                expenses__activity_report__isnull=True,
            ).exclude(
                pk__in=ActivityReport.objects.values('activity_id')
            ).distinct().select_related('project')[:8]

            # unlinked expense ต่อ activity สำหรับ tooltip
            unlinked_counts = {
                row['activity_id']: row['cnt']
                for row in Expense.objects.filter(
                    activity__in=scoped,
                    status='approved',
                    activity_report__isnull=True,
                ).values('activity_id').annotate(cnt=Sum('id') - Sum('id') + Sum('id'))
            }
            # simpler: just count
            from django.db.models import Count as _Count
            unlinked_counts = {
                row['activity_id']: row['cnt']
                for row in Expense.objects.filter(
                    activity__in=scoped,
                    status='approved',
                    activity_report__isnull=True,
                ).values('activity_id').annotate(cnt=_Count('id'))
            }
            for act in no_report_acts:
                act.unlinked_expense_count = unlinked_counts.get(act.pk, 0)

            # 4. มี expense แต่ยังไม่ระบุแหล่งเงิน (budget_source='')
            no_source_acts = scoped.filter(
                expenses__status__in=['pending', 'approved'],
                expenses__budget_source='',
            ).distinct().select_related('project')[:8]

            no_source_counts = {
                row['activity_id']: row['cnt']
                for row in Expense.objects.filter(
                    activity__in=scoped,
                    status__in=['pending', 'approved'],
                    budget_source='',
                ).values('activity_id').annotate(cnt=_Count('id'))
            }
            for act in no_source_acts:
                act.no_source_expense_count = no_source_counts.get(act.pk, 0)

            # 5. ถึงเวลาดำเนินการแล้ว แต่ยังไม่เริ่ม (start_date <= today <= end_date, status=pending)
            not_started_acts = scoped.filter(
                start_date__lte=today,
                end_date__gte=today,
                status='pending',
            ).select_related('project').order_by('start_date')[:8]

            attention = {
                'overdue_acts': overdue_acts,
                'overdue_count': scoped.filter(end_date__lt=today, status__in=['pending', 'in_progress']).count(),
                'budget_full_acts': budget_full_acts,
                'budget_full_count': scoped.filter(
                    status__in=['pending', 'in_progress'], no_budget=False, allocated_budget__gt=0,
                ).annotate(ann_spent=Sum('expenses__amount', filter=Q(expenses__status='approved'))
                ).filter(ann_spent__gte=F('allocated_budget')).count(),
                'no_report_acts': no_report_acts,
                'no_report_count': scoped.filter(
                    expenses__status='approved',
                    expenses__activity_report__isnull=True,
                ).exclude(pk__in=ActivityReport.objects.values('activity_id')).distinct().count(),
                'no_source_acts': no_source_acts,
                'no_source_count': scoped.filter(
                    expenses__status__in=['pending', 'approved'],
                    expenses__budget_source='',
                ).distinct().count(),
                'not_started_acts': not_started_acts,
                'not_started_count': scoped.filter(
                    start_date__lte=today,
                    end_date__gte=today,
                    status='pending',
                ).count(),
            }

        context.update({
            'projects_count': projects.count(),
            'active_projects_count': active_projects.count(),
            'total_budget': total_budget,
            'total_spent': total_spent,
            'remaining_budget': total_budget - total_spent,
            'budget_usage': budget_usage,
            'pending_approvals': pending_approvals,
            'recent_expenses': recent_expenses,
            'upcoming_activities': upcoming_activities,
            'projects': active_projects[:10],
            'role': role,
            'attention': attention,
        })

    return render(request, 'dashboard/index.html', context)


@login_required
def executive(request):
    if hasattr(request.user, 'profile') and request.user.profile.role not in ('planner', 'head', 'admin'):
        from django.shortcuts import redirect
        return redirect('dashboard:index')
    today = timezone.now().date()

    # Active fiscal year
    fiscal_year = FiscalYear.objects.filter(is_active=True).first()

    # All projects (admin sees all, others see by scope — but exec dashboard shows all)
    all_projects = Project.objects.select_related('department', 'fiscal_year')
    if fiscal_year:
        all_projects = all_projects.filter(fiscal_year=fiscal_year)

    total_projects = all_projects.count()
    active_projects = all_projects.filter(status='active').count()
    completed_projects = all_projects.filter(status='completed').count()
    not_started_projects = all_projects.filter(status='not_started').count()
    draft_projects = all_projects.filter(status__in=['draft', 'cancelled']).count()

    # Budget totals
    total_budget = all_projects.aggregate(t=Sum('total_budget'))['t'] or 0
    total_spent = Expense.objects.filter(
        activity__project__in=all_projects, status='approved'
    ).aggregate(t=Sum('amount'))['t'] or 0
    remaining = total_budget - total_spent
    budget_pct = float(total_spent / total_budget * 100) if total_budget > 0 else 0

    # Pending expenses
    pending_expenses = Expense.objects.filter(
        activity__project__in=all_projects, status='pending'
    ).count()

    # Budget by source type
    budget_sources = ProjectBudgetSource.objects.filter(
        project__in=all_projects
    ).values('source_type').annotate(total=Sum('amount'))
    source_map = {s['source_type']: s['total'] for s in budget_sources}

    spent_by_source = {}
    for src in ['government', 'accumulated', 'revenue']:
        spent_by_source[src] = Expense.objects.filter(
            activity__project__in=all_projects,
            status='approved',
            budget_source=src,
        ).aggregate(t=Sum('amount'))['t'] or 0

    source_breakdown = []
    source_labels = {'government': 'เงินแผ่นดิน', 'accumulated': 'เงินสะสม', 'revenue': 'เงินรายได้'}
    source_colors = {'government': 'blue', 'accumulated': 'yellow', 'revenue': 'green'}
    for src in ['government', 'accumulated', 'revenue']:
        src_budget = float(source_map.get(src, 0))
        src_spent = float(spent_by_source.get(src, 0))
        src_remaining = src_budget - src_spent
        src_pct = round(src_spent / src_budget * 100, 1) if src_budget > 0 else 0
        if src_budget > 0:
            source_breakdown.append({
                'key': src,
                'label': source_labels[src],
                'color': source_colors[src],
                'budget': src_budget,
                'spent': src_spent,
                'remaining': src_remaining,
                'pct': src_pct,
            })

    # Budget by department — เฉพาะแผนก (ไม่รวมผู้บริหาร/หัวหน้าสำนักงาน)
    departments = Department.objects.filter(name__startswith='แผนก').order_by('code')
    dept_stats = []
    for dept in departments:
        dept_projects = all_projects.filter(department=dept)
        d_budget = dept_projects.aggregate(t=Sum('total_budget'))['t'] or 0
        d_spent = Expense.objects.filter(
            activity__project__in=dept_projects, status='approved'
        ).aggregate(t=Sum('amount'))['t'] or 0
        d_pct = float(d_spent / d_budget * 100) if d_budget > 0 else 0
        dept_stats.append({
            'dept': dept,
            'budget': d_budget,
            'spent': d_spent,
            'remaining': d_budget - d_spent,
            'pct': round(d_pct, 1),
        })
    # แสดงทุกแผนก รวมถึงที่ยังไม่มีงบประมาณ

    # Attention items (all scope)
    all_activities = Activity.objects.filter(project__in=all_projects)

    overdue_count = all_activities.filter(
        end_date__lt=today, status__in=['pending', 'in_progress']
    ).count()
    overdue_list = all_activities.filter(
        end_date__lt=today, status__in=['pending', 'in_progress']
    ).select_related('project').order_by('end_date')[:5]

    no_report_qs = all_activities.filter(
        expenses__status='approved',
        expenses__activity_report__isnull=True,
    ).exclude(pk__in=ActivityReport.objects.values('activity_id')).distinct()
    no_report_count = no_report_qs.count()
    no_report_list = no_report_qs.select_related('project').order_by('project__name')[:5]

    no_source_count = all_activities.filter(
        expenses__status__in=['pending', 'approved'],
        expenses__budget_source='',
    ).distinct().count()

    # ถึงเวลาดำเนินการแล้ว แต่ยังไม่เริ่ม
    not_started_count = all_activities.filter(
        start_date__lte=today,
        end_date__gte=today,
        status='pending',
    ).count()
    not_started_list = all_activities.filter(
        start_date__lte=today,
        end_date__gte=today,
        status='pending',
    ).select_related('project').order_by('start_date')[:5]

    # Top projects by budget usage
    top_projects = []
    for proj in all_projects.filter(total_budget__gt=0):
        pct = proj.budget_usage_percent
        if pct > 0:
            top_projects.append({'project': proj, 'pct': round(pct, 1)})
    top_projects = sorted(top_projects, key=lambda x: -x['pct'])[:6]

    # Recent expenses
    recent_expenses = Expense.objects.filter(
        activity__project__in=all_projects
    ).select_related('activity__project', 'created_by').order_by('-created_at')[:6]

    # Chart data (JSON)
    chart_source = json.dumps({
        'labels': ['เงินแผ่นดิน', 'เงินสะสม', 'เงินรายได้'],
        'data': [
            float(source_map.get('government', 0)),
            float(source_map.get('accumulated', 0)),
            float(source_map.get('revenue', 0)),
        ],
    })
    chart_dept = json.dumps({
        'labels': [d['dept'].name for d in dept_stats],
        'spent': [float(d['spent']) for d in dept_stats],
        'budget': [float(d['budget']) for d in dept_stats],
    })
    chart_status = json.dumps({
        'labels': ['กำลังดำเนินการ', 'รอดำเนินการ', 'เสร็จสิ้น', 'ร่าง/ยกเลิก'],
        'data': [active_projects, not_started_projects, completed_projects, draft_projects],
    })

    context = {
        'fiscal_year': fiscal_year,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'not_started_projects': not_started_projects,
        'draft_projects': draft_projects,
        'total_budget': total_budget,
        'total_spent': total_spent,
        'remaining': remaining,
        'budget_pct': round(budget_pct, 1),
        'pending_expenses': pending_expenses,
        'source_map': source_map,
        'spent_by_source': spent_by_source,
        'source_breakdown': source_breakdown,
        'dept_stats': dept_stats,
        'overdue_count': overdue_count,
        'overdue_list': overdue_list,
        'no_report_count': no_report_count,
        'no_report_list': no_report_list,
        'no_source_count': no_source_count,
        'not_started_count': not_started_count,
        'not_started_list': not_started_list,
        'top_projects': top_projects,
        'recent_expenses': recent_expenses,
        'today': today,
        'chart_source': chart_source,
        'chart_dept': chart_dept,
        'chart_status': chart_status,
    }
    return render(request, 'dashboard/executive.html', context)


@login_required
def my_tasks(request):
    user = request.user
    today = timezone.now().date()
    soon = today + timedelta(days=7)

    # Activities where user is responsible or notify
    my_activities = Activity.objects.filter(
        Q(responsible_persons=user) | Q(notify_persons=user),
        status__in=['pending', 'in_progress'],
    ).distinct().select_related('project')

    # Sort: overdue first, then ending soon, then rest
    overdue = my_activities.filter(end_date__lt=today)
    ending_soon = my_activities.filter(end_date__gte=today, end_date__lte=soon)
    active = my_activities.filter(end_date__gt=soon, status='in_progress')
    pending_acts = my_activities.filter(end_date__gt=soon, status='pending')

    # My pending expenses (created by me, still pending)
    my_pending_expenses = Expense.objects.filter(
        created_by=user, status='pending'
    ).select_related('activity__project').order_by('-created_at')[:10]

    # For head/admin: expenses pending approval
    role = getattr(getattr(user, 'profile', None), 'role', 'staff')
    pending_for_approval = None
    if role in ('head', 'admin'):
        pending_for_approval = get_expenses_for_user(user).filter(
            status='pending'
        ).select_related('activity__project', 'created_by').order_by('-created_at')[:15]

    context = {
        'today': today,
        'soon': soon,
        'overdue_activities': overdue,
        'ending_soon_activities': ending_soon,
        'active_activities': active,
        'pending_activities': pending_acts,
        'my_pending_expenses': my_pending_expenses,
        'pending_for_approval': pending_for_approval,
        'role': role,
    }
    return render(request, 'dashboard/my_tasks.html', context)
