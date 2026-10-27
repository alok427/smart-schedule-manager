from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User

admin.site.site_header = "Smart Schedule Manager Administration"
admin.site.site_title = "Smart Schedule Manager"
admin.site.index_title = "College Timetable Management"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "department", "is_active")
    list_filter = ("role", "department", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Smart Schedule Manager", {"fields": ("role", "department", "phone_number", "must_change_password")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Smart Schedule Manager", {"fields": ("role", "department", "phone_number", "email")}),
    )
