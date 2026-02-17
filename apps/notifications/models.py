from django.conf import settings
from django.db import models


class LINENotificationLog(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('budget_alert', 'แจ้งเตือนงบประมาณ'),
        ('deadline', 'แจ้งเตือนกำหนดส่ง'),
        ('status_change', 'เปลี่ยนสถานะ'),
        ('expense_approved', 'อนุมัติรายการเบิกจ่าย'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='line_notifications',
        verbose_name='ผู้ใช้',
    )
    message = models.TextField('ข้อความ')
    notification_type = models.CharField(
        'ประเภทการแจ้งเตือน',
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
    )
    is_sent = models.BooleanField('ส่งแล้ว', default=False)
    sent_at = models.DateTimeField('ส่งเมื่อ', null=True, blank=True)
    related_project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='โครงการที่เกี่ยวข้อง',
    )
    related_activity = models.ForeignKey(
        'projects.Activity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='กิจกรรมที่เกี่ยวข้อง',
    )
    created_at = models.DateTimeField('สร้างเมื่อ', auto_now_add=True)

    class Meta:
        verbose_name = 'ประวัติการแจ้งเตือน LINE'
        verbose_name_plural = 'ประวัติการแจ้งเตือน LINE'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.get_notification_type_display()} ({self.created_at})'
