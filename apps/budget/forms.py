from django import forms
from django.core.exceptions import ValidationError

from .models import Expense

TAILWIND_INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500'


def _apply_tailwind(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.Textarea):
            widget.attrs.setdefault('class', TAILWIND_INPUT)
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault('class', TAILWIND_INPUT)
        else:
            widget.attrs.setdefault('class', TAILWIND_INPUT)


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['activity', 'description', 'amount', 'expense_date', 'receipt_number']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_tailwind(self)

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
