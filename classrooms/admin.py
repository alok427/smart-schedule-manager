from django.contrib import admin

from .models import Classroom, RoomAvailability, RoomBooking


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("room_number", "building", "room_type", "capacity", "department", "is_active")
    list_filter = ("room_type", "department", "is_active", "building")
    search_fields = ("room_number", "building")


@admin.register(RoomAvailability)
class RoomAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("classroom", "day", "start_time", "end_time", "reason")
    list_filter = ("day",)


@admin.register(RoomBooking)
class RoomBookingAdmin(admin.ModelAdmin):
    list_display = ("classroom", "date", "start_time", "end_time", "reason", "booked_by")
    list_filter = ("date",)
    date_hierarchy = "date"
