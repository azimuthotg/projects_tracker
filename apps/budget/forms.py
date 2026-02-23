from django import forms
from django.core.exceptions import ValidationError

from .models import Expense

TAILWIND_INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500'
TAILWIND_FILE = (
    'w-full text-sm text-gray-600 '
    'file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 '
    'file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 '
    'hover:file:bg-blue-100 cursor-pointer'
)

ALLOWED_RECEIPT_TYPES = {
    'application/pdf': b'%PDF',
    'image/jpeg': b'\xff\xd8\xff',
    'image/png': b'\x89PNG',
}


def _apply_tailwind(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.ClearableFileInput):
            widget.attrs.setdefault('class', TAILWIND_FILE)
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault('class', TAILWIND_INPUT)
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault('class', TAILWIND_INPUT)
        else:
            widget.attrs.setdefault('class', TAILWIND_INPUT)


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['activity', 'description', 'amount', 'expense_date', 'receipt_number', 'receipt_file']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'receipt_file': forms.ClearableFileInput(attrs={'accept': 'application/pdf,image/jpeg,image/png'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_tailwind(self)

    def clean_receipt_file(self):
        f = self.cleaned_data.get('receipt_file')
        if not f or not hasattr(f, 'content_type'):
            return f
        if f.content_type not in ALLOWED_RECEIPT_TYPES:
            raise ValidationError('อนุญาตเฉพาะไฟล์ PDF, JPG หรือ PNG เท่านั้น')
        if f.size > 20 * 1024 * 1024:
            raise ValidationError('ขนาดไฟล์ต้องไม่เกิน 20 MB')
        # ตรวจ magic bytes
        f.seek(0)
        header = f.read(4)
        f.seek(0)
        expected = ALLOWED_RECEIPT_TYPES[f.content_type]
        if not header.startswith(expected):
            raise ValidationError('ไฟล์ไม่ตรงกับประเภทที่ระบุ')
        return f

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('จำนวนเงินต้องมากกว่า 0')
        return amount

    def clean(self):
        cleaned_data = super().clean()
        activity = cleaned_data.get('activity')
        amount = cleaned_data.get('amount')

        if activity and amount:
            remaining = activity.remaining_budget
            if self.instance.pk and self.instance.status == 'pending':
                remaining += self.instance.amount
            if amount > remaining:
                raise ValidationError(
                    f'จำนวนเงินเกินงบประมาณคงเหลือของกิจกรรม '
                    f'(คงเหลือ {remaining:,.2f} บาท)'
                )
        return cleaned_data


class ExpenseApprovalForm(forms.Form):
    ACTION_CHOICES = [
        ('approved', 'อนุมัติ'),
        ('rejected', 'ไม่อนุมัติ'),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.HiddenInput())
    remark = forms.CharField(
        label='หมายเหตุ',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': TAILWIND_INPUT}),
    )
