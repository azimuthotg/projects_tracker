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
        ('head', 'หัวหน้างาน'),
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
