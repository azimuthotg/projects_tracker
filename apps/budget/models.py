from django.conf import settings
from django.db import models


class Expense(models.Model):
    STATUS_CHOICES = [
        ('pending', 'รอการอนุมัติ'),
        ('approved', 'อนุมัติ'),
        ('rejected', 'ไม่อนุมัติ'),
    ]

    activity = models.ForeignKey(
        'projects.Activity',
        on_delete=models.CASCADE,
        related_name='expenses',
        verbose_name='กิจกรรม',
    )
    description = models.CharField('รายละเอียด', max_length=500)
    amount = models.DecimalField('จำนวนเงิน', max_digits=12, decimal_places=2)
    expense_date = models.DateField('วันที่เบิกจ่าย')
    receipt_number = models.CharField('เลขที่ใบเสร็จ', max_length=100, blank=True)
    receipt_file = models.FileField(
        'ไฟล์หลักฐาน (PDF/รูปภาพ)',
        upload_to='expenses/receipts/',
        blank=True,
        null=True,
    )
    activity_report = models.ForeignKey(
        'projects.ActivityReport',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
        verbose_name='กิจกรรมย่อย (ครั้งที่)',
    )
    status = models.CharField('สถานะ', max_length=10, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_expenses',
        verbose_name='สร้างโดย',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses',
        verbose_name='อนุมัติโดย',
    )
    approved_at = models.DateTimeField('อนุมัติเมื่อ', null=True, blank=True)
    remark = models.TextField('หมายเหตุ', blank=True)
    created_at = models.DateTimeField('สร้างเมื่อ', auto_now_add=True)
    updated_at = models.DateTimeField('แก้ไขเมื่อ', auto_now=True)

    class Meta:
        verbose_name = 'รายการเบิกจ่าย'
        verbose_name_plural = 'รายการเบิกจ่าย'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.activity} - {self.description} ({self.amount:,.2f} บาท)'


class ExpenseComment(models.Model):
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='รายการเบิกจ่าย',
    )
    text = models.TextField('ความเห็น')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='expense_comments',
        verbose_name='สร้างโดย',
    )
    created_at = models.DateTimeField('สร้างเมื่อ', auto_now_add=True)

    class Meta:
        verbose_name = 'ความเห็นรายการเบิกจ่าย'
        verbose_name_plural = 'ความเห็นรายการเบิกจ่าย'
        ordering = ['created_at']

    def __str__(self):
        return f'ความเห็น #{self.pk} บน {self.expense_id}'


class ExpenseAttachment(models.Model):
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='รายการเบิกจ่าย',
    )
    file = models.FileField('ไฟล์แนบ', upload_to='expenses/attachments/')
    original_filename = models.CharField('ชื่อไฟล์', max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='expense_attachments',
        verbose_name='อัพโหลดโดย',
    )
    created_at = models.DateTimeField('อัพโหลดเมื่อ', auto_now_add=True)

    class Meta:
        verbose_name = 'ไฟล์แนบรายการเบิกจ่าย'
        verbose_name_plural = 'ไฟล์แนบรายการเบิกจ่าย'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.original_filename or self.file.name}'


class BudgetTransfer(models.Model):
    BUDGET_TYPE_CHOICES = [
        ('government', 'เงินแผ่นดิน'),
        ('accumulated', 'เงินสะสม'),
        ('revenue', 'เงินรายได้'),
    ]

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        related_name='budget_transfers',
        verbose_name='โครงการ',
    )
    from_activity = models.ForeignKey(
        'projects.Activity',
        on_delete=models.PROTECT,
        related_name='transfers_out',
        verbose_name='โอนจากกิจกรรม',
    )
    to_activity = models.ForeignKey(
        'projects.Activity',
        on_delete=models.PROTECT,
        related_name='transfers_in',
        verbose_name='โอนไปกิจกรรม',
    )
    budget_type = models.CharField('หมวดเงิน', max_length=15, choices=BUDGET_TYPE_CHOICES)
    amount = models.DecimalField('จำนวนเงิน', max_digits=12, decimal_places=2)
    reason = models.TextField('เหตุผล')
    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='budget_transfers',
        verbose_name='โอนโดย',
    )
    created_at = models.DateTimeField('สร้างเมื่อ', auto_now_add=True)

    class Meta:
        verbose_name = 'การโอนงบประมาณ'
        verbose_name_plural = 'การโอนงบประมาณ'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'โอน {self.amount:,.2f} บาท ({self.get_budget_type_display()}) '
            f'จาก {self.from_activity} → {self.to_activity}'
        )
