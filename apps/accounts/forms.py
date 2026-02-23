from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import ApprovedOrganization, Department, UserProfile
from apps.projects.models import FiscalYear

TAILWIND_INPUT = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
TAILWIND_SELECT = TAILWIND_INPUT
TAILWIND_CHECKBOX = 'rounded border-gray-300 text-blue-600 focus:ring-blue-500'


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': TAILWIND_INPUT,
            'placeholder': 'ชื่อผู้ใช้',
        })
        self.fields['password'].widget.attrs.update({
            'class': TAILWIND_INPUT,
            'placeholder': 'รหัสผ่าน',
        })

    def confirm_login_allowed(self, user):
        if not user.is_active:
            profile = getattr(user, 'profile', None)
            if profile:
                if profile.approval_status == 'pending':
                    raise ValidationError(
                        'บัญชีของคุณอยู่ระหว่างรอการอนุมัติจากผู้ดูแลระบบ กรุณารอการยืนยัน',
                        code='pending_approval',
                    )
                if profile.approval_status == 'rejected':
                    raise ValidationError(
                        'บัญชีของคุณถูกปฏิเสธการเข้าใช้งาน กรุณาติดต่อผู้ดูแลระบบ',
                        code='rejected',
                    )
            raise ValidationError(self.error_messages['inactive'], code='inactive')


class ApprovedOrganizationForm(forms.ModelForm):
    class Meta:
        model = ApprovedOrganization
        fields = ['name', 'note', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': TAILWIND_INPUT}),
            'note': forms.TextInput(attrs={'class': TAILWIND_INPUT}),
            'is_active': forms.CheckboxInput(attrs={'class': TAILWIND_CHECKBOX}),
        }


class UserCreateForm(forms.Form):
    username = forms.CharField(label='ชื่อผู้ใช้', max_length=150,
                               widget=forms.TextInput(attrs={'class': TAILWIND_INPUT}))
    first_name = forms.CharField(label='ชื่อ', max_length=150,
                                 widget=forms.TextInput(attrs={'class': TAILWIND_INPUT}))
    last_name = forms.CharField(label='นามสกุล', max_length=150,
                                widget=forms.TextInput(attrs={'class': TAILWIND_INPUT}))
    email = forms.EmailField(label='อีเมล', required=False,
                             widget=forms.EmailInput(attrs={'class': TAILWIND_INPUT}))
    password = forms.CharField(label='รหัสผ่าน', min_length=8,
                               widget=forms.PasswordInput(attrs={'class': TAILWIND_INPUT}))
    password_confirm = forms.CharField(label='ยืนยันรหัสผ่าน', min_length=8,
                                       widget=forms.PasswordInput(attrs={'class': TAILWIND_INPUT}))
    department = forms.ModelChoiceField(label='แผนก', queryset=Department.objects.all(),
                                        required=False,
                                        widget=forms.Select(attrs={'class': TAILWIND_SELECT}))
    role = forms.ChoiceField(label='บทบาท', choices=UserProfile.ROLE_CHOICES,
                             widget=forms.Select(attrs={'class': TAILWIND_SELECT}))

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('ชื่อผู้ใช้นี้มีอยู่แล้ว')
        return username

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('password')
        pw2 = cleaned.get('password_confirm')
        if pw and pw2 and pw != pw2:
            self.add_error('password_confirm', 'รหัสผ่านไม่ตรงกัน')
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data.get('email', ''),
        )
        UserProfile.objects.create(
            user=user,
            department=data.get('department'),
            role=data['role'],
        )
        return user


class UserEditForm(forms.Form):
    first_name = forms.CharField(label='ชื่อ', max_length=150,
                                 widget=forms.TextInput(attrs={'class': TAILWIND_INPUT}))
    last_name = forms.CharField(label='นามสกุล', max_length=150,
                                widget=forms.TextInput(attrs={'class': TAILWIND_INPUT}))
    email = forms.EmailField(label='อีเมล', required=False,
                             widget=forms.EmailInput(attrs={'class': TAILWIND_INPUT}))
    department = forms.ModelChoiceField(label='แผนก', queryset=Department.objects.all(),
                                        required=False,
                                        widget=forms.Select(attrs={'class': TAILWIND_SELECT}))
    role = forms.ChoiceField(label='บทบาท', choices=UserProfile.ROLE_CHOICES,
                             widget=forms.Select(attrs={'class': TAILWIND_SELECT}))
    is_active = forms.BooleanField(label='เปิดใช้งาน', required=False,
                                   widget=forms.CheckboxInput(attrs={'class': TAILWIND_CHECKBOX}))
    line_user_id = forms.CharField(
        label='LINE User ID',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': TAILWIND_INPUT,
            'placeholder': 'Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        }),
        help_text='LINE User ID ของผู้ใช้ (เริ่มต้นด้วย U...) ใช้สำหรับรับการแจ้งเตือน',
    )

    def __init__(self, *args, user_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_instance = user_instance
        if user_instance:
            self.fields['first_name'].initial = user_instance.first_name
            self.fields['last_name'].initial = user_instance.last_name
            self.fields['email'].initial = user_instance.email
            self.fields['is_active'].initial = user_instance.is_active
            if hasattr(user_instance, 'profile'):
                self.fields['department'].initial = user_instance.profile.department_id
                self.fields['role'].initial = user_instance.profile.role
                self.fields['line_user_id'].initial = user_instance.profile.line_user_id

    def save(self):
        data = self.cleaned_data
        user = self.user_instance
        user.first_name = data['first_name']
        user.last_name = data['last_name']
        user.email = data.get('email', '')
        user.is_active = data['is_active']
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.department = data.get('department')
        profile.role = data['role']
        profile.line_user_id = data.get('line_user_id', '')
        profile.save()
        return user


class PasswordResetByAdminForm(forms.Form):
    new_password = forms.CharField(label='รหัสผ่านใหม่', min_length=8,
                                   widget=forms.PasswordInput(attrs={'class': TAILWIND_INPUT}))
    new_password_confirm = forms.CharField(label='ยืนยันรหัสผ่านใหม่', min_length=8,
                                           widget=forms.PasswordInput(attrs={'class': TAILWIND_INPUT}))

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('new_password')
        pw2 = cleaned.get('new_password_confirm')
        if pw and pw2 and pw != pw2:
            self.add_error('new_password_confirm', 'รหัสผ่านไม่ตรงกัน')
        return cleaned


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['code', 'name']
        widgets = {
            'code': forms.TextInput(attrs={'class': TAILWIND_INPUT}),
            'name': forms.TextInput(attrs={'class': TAILWIND_INPUT}),
        }


class ProfileNotificationForm(forms.Form):
    notify_budget_alert = forms.BooleanField(
        label='แจ้งเตือนงบประมาณ',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': TAILWIND_CHECKBOX}),
        help_text='รับการแจ้งเตือนเมื่อใช้งบเกินเกณฑ์',
    )
    notify_deadline = forms.BooleanField(
        label='แจ้งเตือนกำหนดส่ง',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': TAILWIND_CHECKBOX}),
        help_text='รับการแจ้งเตือนเมื่อใกล้วันสิ้นสุดกิจกรรม/โครงการ',
    )
    budget_threshold = forms.IntegerField(
        label='เกณฑ์แจ้งเตือนงบ (%)',
        min_value=50,
        max_value=100,
        widget=forms.NumberInput(attrs={'class': TAILWIND_INPUT}),
        help_text='แจ้งเตือนเมื่อใช้งบถึง X% (50–100)',
    )

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        if profile:
            self.fields['notify_budget_alert'].initial = profile.notify_budget_alert
            self.fields['notify_deadline'].initial = profile.notify_deadline
            self.fields['budget_threshold'].initial = profile.budget_threshold

    def save(self, profile):
        data = self.cleaned_data
        profile.notify_budget_alert = data['notify_budget_alert']
        profile.notify_deadline = data['notify_deadline']
        profile.budget_threshold = data['budget_threshold']
        profile.save(update_fields=['notify_budget_alert', 'notify_deadline', 'budget_threshold'])
        return profile


class FiscalYearForm(forms.ModelForm):
    class Meta:
        model = FiscalYear
        fields = ['year', 'start_date', 'end_date', 'is_active']
        widgets = {
            'year': forms.NumberInput(attrs={'class': TAILWIND_INPUT}),
            'start_date': forms.DateInput(attrs={'class': TAILWIND_INPUT, 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': TAILWIND_INPUT, 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': TAILWIND_CHECKBOX}),
        }
