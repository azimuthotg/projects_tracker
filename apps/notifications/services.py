"""LINE Messaging API service."""
import json
import logging
from datetime import timezone as dt_timezone

import urllib.request
import urllib.error

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class LINEService:
    BASE_URL = "https://api.line.me/v2/bot"

    def _headers(self):
        token = getattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN', '')
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        }

    def _post(self, endpoint, payload):
        """POST to LINE API. Returns True on success, False on failure."""
        token = getattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN', '')
        if not token or token == 'your_line_channel_access_token':
            logger.warning("LINE_CHANNEL_ACCESS_TOKEN not configured — skipping send")
            return False

        url = f"{self.BASE_URL}{endpoint}"
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=self._headers(), method='POST')
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            logger.error("LINE API HTTP %s at %s: %s", e.code, endpoint, body)
            return False
        except Exception as e:
            logger.error("LINE API error at %s: %s", endpoint, e)
            return False

    def push_text(self, line_user_id, text):
        """Send a plain text push message. Returns bool."""
        return self._post('/message/push', {
            'to': line_user_id,
            'messages': [{'type': 'text', 'text': text}],
        })

    def push_flex(self, line_user_id, alt_text, flex_contents):
        """Send a Flex Message push. Returns bool."""
        return self._post('/message/push', {
            'to': line_user_id,
            'messages': [{
                'type': 'flex',
                'altText': alt_text,
                'contents': flex_contents,
            }],
        })

    # ── High-level helpers ──────────────────────────────────────────

    def send_budget_alert(self, user, activity, percent):
        """Send budget threshold alert via Flex Message."""
        from apps.notifications.models import LINENotificationLog

        line_user_id = user.profile.line_user_id
        project = activity.project
        spent = activity.total_spent
        allocated = activity.allocated_budget

        # Color based on %
        if percent >= 100:
            bar_color = '#EF4444'  # red-500
            label_color = '#EF4444'
        elif percent >= 90:
            bar_color = '#F97316'  # orange-500
            label_color = '#F97316'
        else:
            bar_color = '#EAB308'  # yellow-500
            label_color = '#D97706'

        bar_width = min(int(percent), 100)

        alt_text = f"แจ้งเตือน: ใช้งบกิจกรรม {percent:.0f}%"
        flex_contents = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1E3A5F",
                "contents": [
                    {
                        "type": "text",
                        "text": "⚠️ แจ้งเตือนงบประมาณ",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "weight": "bold",
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": activity.name,
                        "size": "md",
                        "weight": "bold",
                        "color": "#1F2937",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": f"โครงการ: {project.name}",
                        "size": "xs",
                        "color": "#6B7280",
                        "wrap": True,
                    },
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "contents": [
                                    {"type": "text", "text": "ใช้แล้ว", "size": "xs", "color": "#9CA3AF"},
                                    {"type": "text", "text": f"{spent:,.2f} ฿", "size": "sm", "weight": "bold", "color": "#1F2937"},
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "contents": [
                                    {"type": "text", "text": "ทั้งหมด", "size": "xs", "color": "#9CA3AF"},
                                    {"type": "text", "text": f"{allocated:,.2f} ฿", "size": "sm", "weight": "bold", "color": "#1F2937"},
                                ]
                            },
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": "#F3F4F6",
                                "height": "8px",
                                "cornerRadius": "4px",
                                "contents": [
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "backgroundColor": bar_color,
                                        "height": "8px",
                                        "cornerRadius": "4px",
                                        "width": f"{bar_width}%",
                                        "contents": [],
                                    }
                                ]
                            },
                            {
                                "type": "text",
                                "text": f"{percent:.1f}% ของงบกิจกรรม",
                                "size": "xs",
                                "color": label_color,
                                "weight": "bold",
                                "margin": "xs",
                            }
                        ]
                    }
                ]
            }
        }

        message_text = f"แจ้งเตือน: กิจกรรม {activity.name} ใช้งบ {percent:.1f}% ({spent:,.2f}/{allocated:,.2f} ฿)"
        is_sent = self.push_flex(line_user_id, alt_text, flex_contents)

        LINENotificationLog.objects.create(
            user=user,
            message=message_text,
            notification_type='budget_alert',
            is_sent=is_sent,
            sent_at=timezone.now() if is_sent else None,
            related_project=project,
            related_activity=activity,
        )
        return is_sent

    def send_deadline_alert(self, user, obj, days_left, obj_type='activity'):
        """Send deadline reminder. obj = Activity or Project."""
        from apps.notifications.models import LINENotificationLog

        line_user_id = user.profile.line_user_id
        end_date_str = obj.end_date.strftime('%d/%m/%Y')
        name = obj.name
        text = f"⏰ แจ้งเตือน: {name} จะสิ้นสุดใน {days_left} วัน ({end_date_str})"

        is_sent = self.push_text(line_user_id, text)

        kwargs = dict(
            user=user,
            message=text,
            notification_type='deadline',
            is_sent=is_sent,
            sent_at=timezone.now() if is_sent else None,
        )
        if obj_type == 'activity':
            kwargs['related_activity'] = obj
            kwargs['related_project'] = obj.project
        else:
            kwargs['related_project'] = obj

        LINENotificationLog.objects.create(**kwargs)
        return is_sent

    def send_expense_notification(self, user, expense, action):
        """Notify expense creator when approved/rejected."""
        from apps.notifications.models import LINENotificationLog

        line_user_id = user.profile.line_user_id
        approver = expense.approved_by
        approver_name = approver.get_full_name() if approver else 'ผู้ดูแลระบบ'

        if action == 'approved':
            icon = '✅'
            action_th = 'อนุมัติแล้ว'
        else:
            icon = '❌'
            action_th = 'ถูกปฏิเสธ'

        text = (
            f"{icon} รายการเบิกจ่าย: {expense.description}\n"
            f"จำนวน: {expense.amount:,.2f} ฿\n"
            f"สถานะ: {action_th}\n"
            f"โดย: {approver_name}"
        )

        is_sent = self.push_text(line_user_id, text)

        LINENotificationLog.objects.create(
            user=user,
            message=text,
            notification_type='expense_approved',
            is_sent=is_sent,
            sent_at=timezone.now() if is_sent else None,
            related_activity=expense.activity,
            related_project=expense.activity.project,
        )
        return is_sent

    def send_activity_start_reminder(self, user, activity):
        """Remind that activity start date has passed but status is still not_started/pending."""
        from apps.notifications.models import LINENotificationLog

        line_user_id = user.profile.line_user_id
        text = (
            f"📌 แจ้งเตือน: กิจกรรม {activity.name}\n"
            f"ถึงวันเริ่มต้นแล้ว ({activity.start_date.strftime('%d/%m/%Y')}) "
            f"แต่ยังไม่เริ่มดำเนินการ"
        )

        is_sent = self.push_text(line_user_id, text)

        LINENotificationLog.objects.create(
            user=user,
            message=text,
            notification_type='deadline',
            is_sent=is_sent,
            sent_at=timezone.now() if is_sent else None,
            related_activity=activity,
            related_project=activity.project,
        )
        return is_sent

    def send_status_change(self, user, obj, obj_type, old_status, new_status, status_display):
        """Notify user that project/activity status has changed."""
        from apps.notifications.models import LINENotificationLog

        line_user_id = user.profile.line_user_id
        if obj_type == 'activity':
            project = obj.project
            text = (
                f"🔄 สถานะกิจกรรมเปลี่ยนแปลง\n"
                f"กิจกรรม: {obj.name}\n"
                f"โครงการ: {project.name}\n"
                f"สถานะใหม่: {status_display}"
            )
            kwargs = dict(related_activity=obj, related_project=project)
        else:
            text = (
                f"🔄 สถานะโครงการเปลี่ยนแปลง\n"
                f"โครงการ: {obj.name}\n"
                f"สถานะใหม่: {status_display}"
            )
            kwargs = dict(related_project=obj)

        is_sent = self.push_text(line_user_id, text)
        LINENotificationLog.objects.create(
            user=user,
            message=text,
            notification_type='status_change',
            is_sent=is_sent,
            sent_at=timezone.now() if is_sent else None,
            **kwargs,
        )
        return is_sent

    def send_manual_notify(self, user, message, project=None, activity=None):
        """Send a manual free-text notification to a user."""
        from apps.notifications.models import LINENotificationLog

        line_user_id = user.profile.line_user_id
        is_sent = self.push_text(line_user_id, message)
        LINENotificationLog.objects.create(
            user=user,
            message=message,
            notification_type='status_change',
            is_sent=is_sent,
            sent_at=timezone.now() if is_sent else None,
            related_project=project,
            related_activity=activity,
        )
        return is_sent
