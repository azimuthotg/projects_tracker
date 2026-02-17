# CLAUDE.md — Project Plan & Budget Tracking System

## Project Overview

You are developing a **Project Plan & Budget Tracking System** for the Academic Resource Center, Nakhon Phanom University (สำนักวิทยบริการ มหาวิทยาลัยนครพนม).

This is a Django web application that allows all staff to view their assigned projects, track budget per activity in real-time, record expenses, and receive automated LINE notifications.

## Problem Being Solved

- The existing ERP only allows planning officers to view project data — other staff cannot access it
- Staff rely on paper documents (hardcopy) which can be lost
- No way to know remaining budget per activity before starting next activity
- No automated notifications for budget alerts or deadlines

## Tech Stack

- **Backend:** Django 5.1+ / Python 3.12+
- **Database:** MySQL 8.0+ (charset: utf8mb4)
- **Frontend:** Tailwind CSS 3.x (via CDN), Django templates
- **Task Queue:** Celery 5.4+ with Redis 7.x as broker
- **Notifications:** LINE Messaging API v2 (Push + Flex Messages)
- **App Server:** Gunicorn behind Nginx
- **Target OS:** Ubuntu Server 24.04 LTS

## Project Structure

```
project_tracker/
├── manage.py
├── requirements.txt
├── .env
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── wsgi.py
│   └── celery.py
├── apps/
│   ├── accounts/        # Auth, UserProfile, Department, LINE linking
│   ├── projects/        # FiscalYear, Project, Activity CRUD
│   ├── budget/          # Expense recording & approval, signals
│   ├── notifications/   # LINE service, Celery tasks, webhook
│   ├── reports/         # Budget reports, Excel/PDF export
│   └── dashboard/       # Dashboard views per role
├── templates/
│   ├── base.html
│   └── components/      # sidebar, navbar, budget_card, etc.
├── static/
└── deploy/              # nginx.conf, systemd units, deploy.sh
```

## Database Models

### accounts app
- **Department**: name, code (unique)
- **UserProfile** (OneToOne → User): department (FK), role (staff/planner/head/admin), line_user_id, notify_budget_alert, notify_deadline, budget_threshold (default 80%)

### projects app
- **FiscalYear**: year (unique, e.g. 2568), start_date, end_date, is_active
- **Project**: fiscal_year (FK), department (FK), project_code (unique), name, description, total_budget (Decimal 12,2), start_date, end_date, status (draft/active/completed/cancelled), responsible_person (FK User), created_by (FK User)
  - Properties: `total_allocated`, `total_spent`, `remaining_budget`, `budget_usage_percent`
- **Activity**: project (FK), activity_number, name, description, allocated_budget (Decimal 12,2), start_date, end_date, status (pending/in_progress/completed/cancelled), responsible_person (FK User)
  - Properties: `total_spent`, `remaining_budget`, `budget_usage_percent`
  - Constraint: unique_together = ["project", "activity_number"]

### budget app
- **Expense**: activity (FK), description, amount (Decimal 12,2), expense_date, receipt_number, status (pending/approved/rejected), created_by (FK User), approved_by (FK User nullable), approved_at, remark
  - Signal: on save with status=approved → check budget threshold → trigger LINE alert

### notifications app
- **LINENotificationLog**: user (FK), message, notification_type (budget_alert/deadline/status_change/expense_approved), is_sent, sent_at, related_project (FK nullable), related_activity (FK nullable)

## RBAC (Role-Based Access Control)

| Role | Slug | Scope |
|------|------|-------|
| เจ้าหน้าที่ | staff | Own projects only (where user is responsible_person) |
| เจ้าหน้าที่แผน | planner | All projects in same department |
| หัวหน้างาน | head | All projects in same department + approve expenses |
| ผู้ดูแลระบบ | admin | All projects, all departments + manage users |

Use `@role_required(["planner", "head", "admin"])` decorator pattern.
Filter querysets based on user role in every view.

## KEY Budget Logic

```python
# Activity.total_spent — SUM of approved expenses
total_spent = self.expenses.filter(status='approved').aggregate(Sum('amount'))['amount__sum'] or 0

# Activity.remaining_budget
remaining = self.allocated_budget - self.total_spent

# Activity.budget_usage_percent
percent = (self.total_spent / self.allocated_budget * 100) if self.allocated_budget > 0 else 0

# CRITICAL: When creating Expense, validate amount <= activity.remaining_budget
# CRITICAL: When Expense approved, check if percent >= user's budget_threshold → send LINE alert
```

## LINE Messaging API

- Use Push Message API (not Reply) for notifications
- Send **Flex Messages** for budget alerts (showing project, activity, amounts, % with color coding)
- Send **Text Messages** for deadline alerts
- Webhook endpoint at `/api/line/webhook/` for receiving events
- Account linking: OAuth2 flow to get LINE User ID → save to UserProfile

### Notification Triggers
1. **Budget alert** — when approved expense pushes usage ≥ threshold (signal-based)
2. **Deadline 7 days** — Celery Beat daily at 08:00
3. **Deadline 3 days** — Celery Beat daily at 08:00
4. **Status change** — when project/activity status changes
5. **Expense approved/rejected** — notify expense creator

## Celery Configuration

```python
# config/celery.py
app = Celery('project_tracker')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Broker: redis://localhost:6379/0
# Beat scheduler: django_celery_beat.schedulers:DatabaseScheduler
```

## Frontend Guidelines

- Use Tailwind CSS via CDN: `<script src="https://cdn.tailwindcss.com"></script>`
- Color scheme: Primary=blue-900, Success=green-500, Warning=yellow-500, Danger=red-500
- Budget progress bars with dynamic color based on % usage
- Responsive design (works on mobile for LINE users clicking notification links)
- Thai language UI throughout
- Components: sidebar (role-aware nav), budget_card, stats_widget, expense_table, activity_timeline

## Development Order

1. **Foundation**: project setup → models → migrations → auth → RBAC → admin → base templates
2. **Core**: dashboard → project CRUD → activity CRUD → budget tracking UI → expense CRUD → approval workflow
3. **Notifications**: LINE service → account linking → budget signals → Celery tasks → deadline alerts → reports
4. **Deploy**: tests → UAT → Ubuntu deployment → SSL → monitoring

## Important Notes

- All monetary fields use `DecimalField(max_digits=12, decimal_places=2)`
- Thai fiscal year: October 1 to September 30 (e.g., ปีงบ 2568 = Oct 2024 - Sep 2025)
- Use `django-environ` for .env configuration
- Use `whitenoise` for static files in production
- All timestamps in Asia/Bangkok timezone
- UI text in Thai, code/comments in English
- Validate that SUM of activity allocated_budgets <= project total_budget
