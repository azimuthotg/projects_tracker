from django.contrib import admin

from .models import LINENotificationLog


@admin.register(LINENotificationLog)
class LINENotificationLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'is_sent', 'sent_at', 'related_project']
    list_filter = ['notification_type', 'is_sent']
    search_fields = ['user__username', 'message']
    raw_id_fields = ['user', 'related_project', 'related_activity']
    date_hierarchy = 'created_at'
