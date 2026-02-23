from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField('ชื่อแผนก', max_length=200)
    code = models.CharField('รหัสแผนก', max_length=20, unique=True)

    class Meta:
        verbose_name = 'แผนก'
        verbose_name_plural = 'แผนก'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('staff', 'เจ้าหน้าที่'),
        ('planner', 'เจ้าหน้าที่แผน'),
        ('head', 'หัวหน้าแผนก'),
        ('admin', 'ผู้ดูแลระบบ'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='ผู้ใช้',
    )
    organization = models.CharField('หน่วยงาน', max_length=255, blank=True,
                                     help_text='ดึงจาก NPU AD อัตโนมัติ')
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name='แผนก',
    )
    role = models.CharField('บทบาท', max_length=10, choices=ROLE_CHOICES, default='staff')

    # NPU AD fields
    SOURCE_CHOICES = [
        ('manual', 'สร้างในระบบ'),
        ('npu_api', 'NPU AD'),
    ]
    npu_citizen_id = models.CharField(
        'เลขบัตรประชาชน', max_length=13, unique=True, null=True, blank=True,
    )
    npu_staff_id = models.CharField('รหัสบุคลากร NPU', max_length=20, blank=True)
    position_title = models.CharField('ตำแหน่ง', max_length=255, blank=True)
    employment_status = models.CharField('สถานะการปฏิบัติงาน', max_length=100, blank=True)
    source = models.CharField('แหล่งข้อมูล', max_length=10, choices=SOURCE_CHOICES, default='manual')
    last_npu_sync = models.DateTimeField('ซิงค์ล่าสุด', null=True, blank=True)

    # Approval status (for NPU AD users from unapproved organizations)
    APPROVAL_CHOICES = [
        ('approved', 'อนุมัติแล้ว'),
        ('pending', 'รอการอนุมัติ'),
        ('rejected', 'ปฏิเสธ'),
    ]
    approval_status = models.CharField(
        'สถานะอนุมัติ', max_length=10,
        choices=APPROVAL_CHOICES, default='approved',
    )

    # LINE & notification fields
    line_user_id = models.CharField('LINE User ID', max_length=50, blank=True)
    notify_budget_alert = models.BooleanField('แจ้งเตือนงบประมาณ', default=True)
    notify_deadline = models.BooleanField('แจ้งเตือนกำหนดส่ง', default=True)
    budget_threshold = models.PositiveIntegerField('เกณฑ์แจ้งเตือนงบ (%)', default=80)

    class Meta:
        verbose_name = 'โปรไฟล์ผู้ใช้'
        verbose_name_plural = 'โปรไฟล์ผู้ใช้'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.get_role_display()})'


class ApprovedOrganization(models.Model):
    """หน่วยงานที่ได้รับอนุมัติให้เข้าใช้ระบบโดยอัตโนมัติ (จาก NPU AD)"""
    name = models.CharField('ชื่อหน่วยงาน', max_length=255, unique=True)
    note = models.CharField('หมายเหตุ', max_length=255, blank=True)
    is_active = models.BooleanField('เปิดใช้งาน', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'หน่วยงานที่อนุมัติอัตโนมัติ'
        verbose_name_plural = 'หน่วยงานที่อนุมัติอัตโนมัติ'
        ordering = ['name']

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    ACTION_CHOICES = [
        # Critical — Auth
        ('LOGIN', 'เข้าสู่ระบบ'),
        ('LOGOUT', 'ออกจากระบบ'),
        ('LOGIN_FAILED', 'เข้าสู่ระบบล้มเหลว'),
        # Critical — Finance
        ('EXPENSE_APPROVE', 'อนุมัติรายการเบิกจ่าย'),
        ('EXPENSE_REJECT', 'ปฏิเสธรายการเบิกจ่าย'),
        # Critical — Project
        ('PROJECT_CREATE', 'สร้างโครงการ'),
        ('PROJECT_UPDATE', 'แก้ไขโครงการ'),
        ('PROJECT_DELETE', 'ลบโครงการ'),
        ('PROJECT_STATUS', 'เปลี่ยนสถานะโครงการ'),
        ('PROJECT_DELETE_REQUEST', 'ขอลบโครงการ'),
        ('PROJECT_DELETE_APPROVE', 'อนุมัติลบโครงการ'),
        ('PROJECT_DELETE_REJECT', 'ปฏิเสธคำขอลบโครงการ'),
        # Critical — Activity
        ('ACTIVITY_CREATE', 'สร้างกิจกรรม'),
        ('ACTIVITY_UPDATE', 'แก้ไขกิจกรรม'),
        # Critical — Expense
        ('EXPENSE_CREATE', 'บันทึกรายการเบิกจ่าย'),
        ('EXPENSE_UPDATE', 'แก้ไขรายการเบิกจ่าย'),
        ('EXPENSE_DELETE', 'ลบรายการเบิกจ่าย'),
        # Important — User management
        ('USER_ROLE_CHANGE', 'เปลี่ยนบทบาทผู้ใช้'),
        ('USER_PASSWORD_RESET', 'รีเซ็ตรหัสผ่าน'),
        ('USER_SOURCE_CHANGE', 'เปลี่ยนแหล่งข้อมูลผู้ใช้'),
        ('USER_TOGGLE_ACTIVE', 'เปิด/ปิดการใช้งานผู้ใช้'),
        ('USER_APPROVE', 'อนุมัติผู้ใช้'),
        ('USER_REJECT', 'ปฏิเสธผู้ใช้'),
    ]

    LEVEL_CRITICAL = 'critical'
    LEVEL_IMPORTANT = 'important'
    LEVEL_CHOICES = [
        ('critical', 'Critical'),
        ('important', 'Important'),
    ]

    # Map action → level
    ACTION_LEVELS = {
        'LOGIN': LEVEL_CRITICAL,
        'LOGOUT': LEVEL_CRITICAL,
        'LOGIN_FAILED': LEVEL_CRITICAL,
        'EXPENSE_APPROVE': LEVEL_CRITICAL,
        'EXPENSE_REJECT': LEVEL_CRITICAL,
        'PROJECT_CREATE': LEVEL_CRITICAL,
        'PROJECT_UPDATE': LEVEL_CRITICAL,
        'PROJECT_DELETE': LEVEL_CRITICAL,
        'PROJECT_STATUS': LEVEL_CRITICAL,
        'PROJECT_DELETE_REQUEST': LEVEL_CRITICAL,
        'PROJECT_DELETE_APPROVE': LEVEL_CRITICAL,
        'PROJECT_DELETE_REJECT': LEVEL_CRITICAL,
        'ACTIVITY_CREATE': LEVEL_CRITICAL,
        'ACTIVITY_UPDATE': LEVEL_CRITICAL,
        'EXPENSE_CREATE': LEVEL_CRITICAL,
        'EXPENSE_UPDATE': LEVEL_CRITICAL,
        'EXPENSE_DELETE': LEVEL_CRITICAL,
        'USER_ROLE_CHANGE': LEVEL_IMPORTANT,
        'USER_PASSWORD_RESET': LEVEL_IMPORTANT,
        'USER_SOURCE_CHANGE': LEVEL_IMPORTANT,
        'USER_TOGGLE_ACTIVE': LEVEL_IMPORTANT,
        'USER_APPROVE': LEVEL_IMPORTANT,
        'USER_REJECT': LEVEL_IMPORTANT,
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name='ผู้ดำเนินการ',
    )
    action = models.CharField('การกระทำ', max_length=30, choices=ACTION_CHOICES, db_index=True)
    level = models.CharField('ระดับ', max_length=10, choices=LEVEL_CHOICES, default='important')
    target_repr = models.CharField('เป้าหมาย', max_length=500, blank=True)
    detail = models.TextField('รายละเอียด', blank=True)
    ip_address = models.GenericIPAddressField('IP Address', null=True, blank=True)
    created_at = models.DateTimeField('เวลา', auto_now_add=True, db_index=True)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs_about',
        verbose_name='ผู้ใช้เป้าหมาย',
    )

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']

    def __str__(self):
        actor = self.user.username if self.user else 'anonymous'
        return f'[{self.action}] by {actor} at {self.created_at}'
