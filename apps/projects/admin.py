from django.contrib import admin

from .models import Activity, FiscalYear, Project, ProjectDeleteRequest


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = ['year', 'start_date', 'end_date', 'is_active']
    list_filter = ['is_active']


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ['activity_number', 'name', 'allocated_budget', 'status']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['project_code', 'name', 'department', 'fiscal_year', 'total_budget', 'status']
    list_filter = ['status', 'fiscal_year', 'department']
    search_fields = ['project_code', 'name']
    raw_id_fields = ['created_by']
    filter_horizontal = ['responsible_persons', 'notify_persons']
    inlines = [ActivityInline]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['project', 'activity_number', 'name', 'allocated_budget', 'status']
    list_filter = ['status', 'project__fiscal_year']
    search_fields = ['name', 'project__name', 'project__project_code']
    filter_horizontal = ['responsible_persons', 'notify_persons']


@admin.register(ProjectDeleteRequest)
class ProjectDeleteRequestAdmin(admin.ModelAdmin):
    list_display = ['project', 'requested_by', 'status', 'requested_at', 'reviewed_by', 'reviewed_at']
    list_filter = ['status', 'requested_at']
    search_fields = ['project__name', 'project__project_code', 'requested_by__username']
    readonly_fields = ['requested_at', 'reviewed_at']
    raw_id_fields = ['project', 'requested_by', 'reviewed_by']
