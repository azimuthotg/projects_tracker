from django.conf import settings
from django.db import models
from django.db.models import Sum


class FiscalYear(models.Model):
    year = models.PositiveIntegerField('ปีงบประมาณ', unique=True)
    start_date = models.DateField('วันที่เริ่ม')
    end_date = models.DateField('วันที่สิ้นสุด')
    is_active = models.BooleanField('ใช้งานอยู่', default=False)

    class Meta:
        verbose_name = 'ปีงบประมาณ'
        verbose_name_plural = 'ปีงบประมาณ'
        ordering = ['-year']

    def __str__(self):
        return f'ปีงบประมาณ {self.year}'


class Project(models.Model):
    STATUS_CHOICES = [
        ('draft', 'ร่าง'),
        ('active', 'ดำเนินการ'),
        ('completed', 'เสร็จสิ้น'),
        ('cancelled', 'ยกเลิก'),
    ]

    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='projects',
        verbose_name='ปีงบประมาณ',
    )
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.PROTECT,
        related_name='projects',
        verbose_name='แผนก',
    )
    project_code = models.CharField('รหัสโครงการ', max_length=50, unique=True)
    name = models.CharField('ชื่อโครงการ', max_length=300)
    description = models.TextField('รายละเอียด', blank=True)
    total_budget = models.DecimalField('งบประมาณรวม', max_digits=12, decimal_places=2)
    start_date = models.DateField('วันที่เริ่ม')
    end_date = models.DateField('วันที่สิ้นสุด')
    status = models.CharField('สถานะ', max_length=10, choices=STATUS_CHOICES, default='draft')
    responsible_persons = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='responsible_projects',
        verbose_name='ผู้รับผิดชอบหลัก',
        blank=True,
    )
    notify_persons = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='notify_projects',
        verbose_name='ตั้งแจ้งเตือน',
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_projects',
        verbose_name='สร้างโดย',
    )
    created_at = models.DateTimeField('สร้างเมื่อ', auto_now_add=True)
    updated_at = models.DateTimeField('แก้ไขเมื่อ', auto_now=True)

    class Meta:
        verbose_name = 'โครงการ'
        verbose_name_plural = 'โครงการ'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project_code} - {self.name}'

    @property
    def total_allocated(self):
        return self.activities.aggregate(
            total=Sum('allocated_budget')
        )['total'] or 0

    @property
    def total_spent(self):
        from apps.budget.models import Expense
        return Expense.objects.filter(
            activity__project=self,
            status='approved',
        ).aggregate(total=Sum('amount'))['total'] or 0

    @property
    def remaining_budget(self):
        return self.total_budget - self.total_spent

    @property
    def budget_usage_percent(self):
        if self.total_budget > 0:
            return float(self.total_spent / self.total_budget * 100)
        return 0


class Activity(models.Model):
    STATUS_CHOICES = [
        ('pending', 'รอดำเนินการ'),
        ('in_progress', 'กำลังดำเนินการ'),
        ('completed', 'เสร็จสิ้น'),
        ('cancelled', 'ยกเลิก'),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='activities',
        verbose_name='โครงการ',
    )
    activity_number = models.PositiveIntegerField('ลำดับกิจกรรม')
    name = models.CharField('ชื่อกิจกรรม', max_length=300)
    description = models.TextField('รายละเอียด', blank=True)
    allocated_budget = models.DecimalField('งบประมาณที่จัดสรร', max_digits=12, decimal_places=2)
    start_date = models.DateField('วันที่เริ่ม')
    end_date = models.DateField('วันที่สิ้นสุด')
    status = models.CharField('สถานะ', max_length=12, choices=STATUS_CHOICES, default='pending')
    responsible_persons = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='responsible_activities',
        verbose_name='ผู้รับผิดชอบกิจกรรม',
        blank=True,
    )
    notify_persons = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='notify_activities',
        verbose_name='ตั้งแจ้งเตือน',
        blank=True,
    )

    class Meta:
        verbose_name = 'กิจกรรม'
        verbose_name_plural = 'กิจกรรม'
        unique_together = ['project', 'activity_number']
        ordering = ['project', 'activity_number']

    def __str__(self):
        return f'{self.project.project_code}-{self.activity_number}: {self.name}'

    @property
    def total_spent(self):
        return self.expenses.filter(
            status='approved'
        ).aggregate(total=Sum('amount'))['total'] or 0

    @property
    def remaining_budget(self):
        return self.allocated_budget - self.total_spent

    @property
    def budget_usage_percent(self):
        if self.allocated_budget > 0:
            return float(self.total_spent / self.allocated_budget * 100)
        return 0
