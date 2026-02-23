from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from .models import Activity, Project, ProjectBudgetSource

User = get_user_model()

TAILWIND_INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500'
TAILWIND_SELECT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500'
TAILWIND_TEXTAREA = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500'
TAILWIND_CHECKBOX_GROUP = 'space-y-1'


TAILWIND_FILE = (
    'w-full text-sm text-gray-600 '
    'file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 '
    'file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 '
    'hover:file:bg-blue-100 cursor-pointer'
)


def _apply_tailwind(form):
    for name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget, forms.CheckboxSelectMultiple):
            widget.attrs.setdefault('class', TAILWIND_CHECKBOX_GROUP)
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault('class', TAILWIND_TEXTAREA)
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault('class', TAILWIND_SELECT)
        elif isinstance(widget, forms.ClearableFileInput):
            widget.attrs.setdefault('class', TAILWIND_FILE)
            widget.attrs.setdefault('accept', 'application/pdf')
        else:
            widget.attrs.setdefault('class', TAILWIND_INPUT)


def _get_user_label(user):
    """Display user as 'ชื่อ-นามสกุล (role)' or fallback to username."""
    full_name = user.get_full_name()
    role_display = ''
    if hasattr(user, 'profile'):
        role_display = user.profile.get_role_display()
    name = full_name or user.username
    if role_display:
        return f'{name} ({role_display})'
    return name


def _get_user_queryset(user):
    """Filter user choices based on requesting user's role."""
    if not hasattr(user, 'profile'):
        return User.objects.none()
    role = user.profile.role
    if role == 'admin':
        return User.objects.filter(is_active=True).select_related('profile')
    else:
        # planner/head: users in same department
        return User.objects.filter(
            is_active=True,
            profile__department=user.profile.department,
        ).select_related('profile')


def _apply_tailwind_formset(formset):
    """Apply tailwind styles to all forms in a formset."""
    for form in formset.forms:
        for name, field in form.fields.items():
            if name == 'DELETE':
                continue
            widget = field.widget
            if isinstance(widget, (forms.Select,)):
                widget.attrs.setdefault('class', TAILWIND_SELECT)
            elif isinstance(widget, forms.CheckboxInput):
                pass
            else:
                widget.attrs.setdefault('class', TAILWIND_INPUT)


ProjectBudgetSourceFormSet = inlineformset_factory(
    Project,
    ProjectBudgetSource,
    fields=['source_type', 'erp_code', 'amount'],
    extra=1,
    can_delete=True,
    min_num=0,
)


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            'fiscal_year', 'department', 'project_code', 'name',
            'description', 'start_date', 'end_date',
            'status', 'document', 'responsible_persons', 'notify_persons',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'responsible_persons': forms.CheckboxSelectMultiple(),
            'notify_persons': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        if user:
            role = getattr(getattr(user, 'profile', None), 'role', 'staff')
            # เฉพาะ planner/admin เท่านั้นที่เลือกแผนกได้
            if role not in ('planner', 'admin'):
                del self.fields['department']
            qs = _get_user_queryset(user)
            self.fields['responsible_persons'].queryset = qs
            self.fields['notify_persons'].queryset = qs
            self.fields['responsible_persons'].label_from_instance = _get_user_label
            self.fields['notify_persons'].label_from_instance = _get_user_label
        _apply_tailwind(self)

    def clean_document(self):
        doc = self.cleaned_data.get('document')
        if doc and hasattr(doc, 'content_type'):
            if doc.content_type != 'application/pdf':
                raise ValidationError('อนุญาตเฉพาะไฟล์ PDF เท่านั้น')
            if doc.size > 20 * 1024 * 1024:
                raise ValidationError('ขนาดไฟล์ต้องไม่เกิน 20 MB')
            # ตรวจ magic bytes ป้องกันการปลอม content-type
            doc.seek(0)
            if doc.read(4) != b'%PDF':
                raise ValidationError('ไฟล์ที่อัปโหลดไม่ใช่ PDF ที่ถูกต้อง')
            doc.seek(0)
        return doc

    def clean_responsible_persons(self):
        persons = self.cleaned_data.get('responsible_persons')
        if not persons:
            raise ValidationError('ต้องเลือกผู้รับผิดชอบอย่างน้อย 1 คน')
        return persons

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise ValidationError('วันที่เริ่มต้นต้องก่อนวันที่สิ้นสุด')
        return cleaned_data


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = [
            'name', 'description',
            'allocated_budget',
            'budget_government', 'budget_accumulated', 'budget_revenue',
            'start_date', 'end_date', 'status',
            'responsible_persons', 'notify_persons',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'responsible_persons': forms.CheckboxSelectMultiple(),
            'notify_persons': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, project=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.project_sources = list(project.budget_sources.all()) if project else []

        if self.project_sources:
            # Budget source mode — ซ่อน allocated_budget, แสดงเฉพาะ source ที่มีในโครงการ
            del self.fields['allocated_budget']
            active_source_types = {s.source_type for s in self.project_sources}
            for st in ['government', 'accumulated', 'revenue']:
                if st not in active_source_types:
                    del self.fields[f'budget_{st}']
        else:
            # Legacy mode — แสดง allocated_budget, ซ่อน source fields
            for st in ['government', 'accumulated', 'revenue']:
                del self.fields[f'budget_{st}']

        if user:
            qs = _get_user_queryset(user)
            self.fields['responsible_persons'].queryset = qs
            self.fields['notify_persons'].queryset = qs
            self.fields['responsible_persons'].label_from_instance = _get_user_label
            self.fields['notify_persons'].label_from_instance = _get_user_label
        _apply_tailwind(self)

    def clean_responsible_persons(self):
        persons = self.cleaned_data.get('responsible_persons')
        if not persons:
            raise ValidationError('ต้องเลือกผู้รับผิดชอบอย่างน้อย 1 คน')
        return persons

    def clean_allocated_budget(self):
        """Legacy mode validation (used when project has no budget sources)."""
        amount = self.cleaned_data['allocated_budget']
        if amount <= 0:
            raise ValidationError('งบประมาณต้องมากกว่า 0')
        if self.project:
            other_allocated = self.project.total_allocated
            if self.instance.pk:
                other_allocated -= self.instance.allocated_budget
            if other_allocated + amount > self.project.total_budget:
                available = self.project.total_budget - other_allocated
                raise ValidationError(
                    f'งบประมาณเกินกว่าที่โครงการกำหนด '
                    f'(เหลือจัดสรรได้ {available:,.2f} บาท)'
                )
        return amount

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise ValidationError('วันที่เริ่มต้นต้องก่อนวันที่สิ้นสุด')

        if self.project_sources:
            # Budget source mode — validate total
            total = sum(
                cleaned_data.get(f'budget_{s.source_type}') or 0
                for s in self.project_sources
            )
            if total <= 0:
                raise ValidationError('ต้องระบุงบประมาณอย่างน้อย 1 หมวดเงิน')
            if self.project:
                other_allocated = self.project.total_allocated
                if self.instance.pk:
                    other_allocated -= self.instance.allocated_budget
                if other_allocated + total > self.project.total_budget:
                    available = self.project.total_budget - other_allocated
                    raise ValidationError(
                        f'งบรวมเกินกว่าที่โครงการกำหนด '
                        f'(เหลือจัดสรรได้ {available:,.2f} บาท)'
                    )
        return cleaned_data
