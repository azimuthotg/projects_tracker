from django.contrib import admin

from .models import Department, UserProfile


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['name', 'code']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'department', 'role', 'source', 'npu_citizen_id', 'position_title', 'employment_status', 'budget_threshold']
    list_filter = ['role', 'department', 'source', 'employment_status']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'npu_citizen_id']
    raw_id_fields = ['user']
    readonly_fields = ['organization', 'last_npu_sync']
