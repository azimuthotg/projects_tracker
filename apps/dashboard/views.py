from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.budget.models import Expense
from apps.budget.utils import get_expenses_for_user
from apps.projects.models import Activity
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
        })

    return render(request, 'dashboard/index.html', context)


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
