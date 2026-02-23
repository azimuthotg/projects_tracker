from django.conf import settings
from django.db import models
from django.db.models import Sum


class ProjectDeleteRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'รอพิจารณา'),
        ('approved', 'อนุมัติ'),
        ('rejected', 'ปฏิเสธ'),
    ]

    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='delete_requests',
        verbose_name='โครงการ',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='project_delete_requests',
        verbose_name='ผู้ขอลบ',
    )
    reason = models.TextField('เหตุผลที่ขอลบ')
    status = models.CharField('สถานะ', max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField('ขอเมื่อ', auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_delete_requests',
        verbose_name='ผู้พิจารณา',
    )
    reviewed_at = models.DateTimeField('พิจารณาเมื่อ', null=True, blank=True)
    review_remark = models.TextField('หมายเหตุ', blank=True)

    class Meta:
        verbose_name = 'คำขอลบโครงการ'
        verbose_name_plural = 'คำขอลบโครงการ'
        ordering = ['-requested_at']

    def __str__(self):
        return f'ขอลบ {self.project} โดย {self.requested_by} ({self.get_status_display()})'


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


SOURCE_CHOICES = [
    ('government', 'เงินแผ่นดิน'),
    ('accumulated', 'เงินสะสม'),
    ('revenue', 'เงินรายได้'),
]


class Project(models.Model):
    STATUS_CHOICES = [
        ('draft', 'ร่าง'),
        ('not_started', 'ยังไม่ดำเนินการ'),
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
    status = models.CharField('สถานะ', max_length=20, choices=STATUS_CHOICES, default='draft')
    document = models.FileField('เอกสารแนบ (PDF)', upload_to='projects/documents/', blank=True, null=True)
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

    def budget_source_summary(self, exclude_activity_pk=None):
        """Returns list of dicts with per-source budget info for activity form display."""
        result = []
        for source in self.budget_sources.all():
            field = f'budget_{source.source_type}'
            qs = self.activities.all()
            if exclude_activity_pk:
                qs = qs.exclude(pk=exclude_activity_pk)
            allocated = qs.aggregate(total=Sum(field))['total'] or 0
            result.append({
                'source_type': source.source_type,
                'label': source.get_source_type_display(),
                'erp_code': source.erp_code,
                'total': source.amount,
                'allocated': allocated,
                'remaining': source.amount - allocated,
            })
        return result

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


class ProjectBudgetSource(models.Model):
    """แหล่งเงินงบประมาณของโครงการ (แผ่นดิน / สะสม / รายได้)"""
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='budget_sources',
        verbose_name='โครงการ',
    )
    source_type = models.CharField('หมวดเงิน', max_length=20, choices=SOURCE_CHOICES)
    erp_code = models.CharField('รหัสโครงการ ERP', max_length=50, blank=True)
    amount = models.DecimalField('งบประมาณ', max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ['project', 'source_type']
        verbose_name = 'แหล่งงบประมาณ'
        verbose_name_plural = 'แหล่งงบประมาณ'
        ordering = ['source_type']

    def __str__(self):
        return f'{self.get_source_type_display()}: {self.amount:,.2f}'

    def get_source_type_display(self):
        return dict(SOURCE_CHOICES).get(self.source_type, self.source_type)


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
    allocated_budget = models.DecimalField('งบประมาณที่จัดสรร (รวม)', max_digits=12, decimal_places=2, default=0)
    budget_government = models.DecimalField('เงินแผ่นดิน', max_digits=12, decimal_places=2, default=0)
    budget_accumulated = models.DecimalField('เงินสะสม', max_digits=12, decimal_places=2, default=0)
    budget_revenue = models.DecimalField('เงินรายได้', max_digits=12, decimal_places=2, default=0)
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

    def save(self, *args, **kwargs):
        total = self.budget_government + self.budget_accumulated + self.budget_revenue
        if total > 0:
            self.allocated_budget = total
        super().save(*args, **kwargs)

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
