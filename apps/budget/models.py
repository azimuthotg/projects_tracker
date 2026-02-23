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
