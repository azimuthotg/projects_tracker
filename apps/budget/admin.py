from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['activity', 'description', 'amount', 'expense_date', 'status', 'created_by', 'approved_by']
    list_filter = ['status', 'expense_date', 'activity__project__fiscal_year']
    search_fields = ['description', 'receipt_number', 'activity__name', 'activity__project__name']
    raw_id_fields = ['activity', 'created_by', 'approved_by']
    date_hierarchy = 'expense_date'
