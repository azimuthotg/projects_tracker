"""Management command: send deadline alerts via LINE."""
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.models import LINENotificationLog
from apps.notifications.services import LINEService
from apps.projects.models import Activity, Project


class Command(BaseCommand):
    help = "Send LINE deadline alerts for activities and projects (run daily at 08:00)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be sent without actually sending',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.localdate()  # Asia/Bangkok

        service = LINEService()
        sent = 0
        skipped_no_line = 0
        skipped_duplicate = 0
        errors = 0

        # ── Activity alerts ──────────────────────────────────────────

        activities = Activity.objects.filter(
            status__in=['not_started', 'pending', 'in_progress'],
            end_date__isnull=False,
        ).select_related('project').prefetch_related('notify_persons__profile')

        for activity in activities:
            days_left = (activity.end_date - today).days

            # Deadline alert: 7 or 3 days left
            if days_left in (7, 3):
                for person in activity.notify_persons.all():
                    profile = getattr(person, 'profile', None)
                    if not profile or not profile.line_user_id:
                        skipped_no_line += 1
                        continue
                    if not profile.notify_deadline:
                        skipped_no_line += 1
                        continue

                    if self._already_sent_today(person, 'deadline', activity=activity, today=today):
                        skipped_duplicate += 1
                        continue

                    if dry_run:
                        self.stdout.write(
                            f"[DRY-RUN] deadline {days_left}d — {person.username} → {activity.name}"
                        )
                        sent += 1
                    else:
                        try:
                            service.send_deadline_alert(person, activity, days_left, obj_type='activity')
                            sent += 1
                        except Exception as e:
                            self.stderr.write(f"ERROR sending to {person.username}: {e}")
                            errors += 1

            # Start reminder: start_date has passed but still not started
            if (activity.start_date and
                    activity.start_date <= today and
                    activity.status in ('not_started', 'pending')):
                for person in activity.notify_persons.all():
                    profile = getattr(person, 'profile', None)
                    if not profile or not profile.line_user_id:
                        skipped_no_line += 1
                        continue
                    if not profile.notify_deadline:
                        skipped_no_line += 1
                        continue

                    if self._already_sent_today(person, 'deadline', activity=activity, today=today):
                        skipped_duplicate += 1
                        continue

                    if dry_run:
                        self.stdout.write(
                            f"[DRY-RUN] start-reminder — {person.username} → {activity.name}"
                        )
                        sent += 1
                    else:
                        try:
                            service.send_activity_start_reminder(person, activity)
                            sent += 1
                        except Exception as e:
                            self.stderr.write(f"ERROR sending to {person.username}: {e}")
                            errors += 1

        # ── Project alerts ───────────────────────────────────────────

        projects = Project.objects.filter(
            status__in=['draft', 'active', 'not_started'],
            end_date__isnull=False,
        ).prefetch_related('notify_persons__profile')

        for project in projects:
            days_left = (project.end_date - today).days

            if days_left in (7, 3):
                for person in project.notify_persons.all():
                    profile = getattr(person, 'profile', None)
                    if not profile or not profile.line_user_id:
                        skipped_no_line += 1
                        continue
                    if not profile.notify_deadline:
                        skipped_no_line += 1
                        continue

                    if self._already_sent_today(person, 'deadline', project=project, today=today):
                        skipped_duplicate += 1
                        continue

                    if dry_run:
                        self.stdout.write(
                            f"[DRY-RUN] project deadline {days_left}d — {person.username} → {project.name}"
                        )
                        sent += 1
                    else:
                        try:
                            service.send_deadline_alert(person, project, days_left, obj_type='project')
                            sent += 1
                        except Exception as e:
                            self.stderr.write(f"ERROR sending to {person.username}: {e}")
                            errors += 1

        suffix = " (dry-run)" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Done{suffix}: sent={sent}, skipped_no_line={skipped_no_line}, "
                f"skipped_duplicate={skipped_duplicate}, errors={errors}"
            )
        )

    def _already_sent_today(self, user, ntype, activity=None, project=None, today=None):
        """Return True if we already sent this notification today."""
        qs = LINENotificationLog.objects.filter(
            user=user,
            notification_type=ntype,
            created_at__date=today,
        )
        if activity is not None:
            qs = qs.filter(related_activity=activity)
        elif project is not None:
            qs = qs.filter(related_project=project, related_activity__isnull=True)
        return qs.exists()
